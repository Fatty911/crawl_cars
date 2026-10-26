import contextlib
import importlib.util
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('download_verified_release', Path(__file__).parents[1] / 'scripts/download_verified_release.py')
downloader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(downloader)


def release(tag, date='2026-10-10T00:00:00Z', *, draft=False, complete=True, prerelease=False):
    return {'tag_name': tag, 'published_at': date, 'draft': draft, 'prerelease': prerelease, 'assets':
            [{'name': name, 'state': 'uploaded', 'size': 12} for name in
             (['manifest.json', 'verified-site.zip'] if complete else ['manifest.json'])]}


RAW_TAG = 'cnb-data-20261015T041723Z-cnb-6as-1k4ujn7mr'


def derived(index, date='2026-10-26T00:00:00Z'):
    return release(f'cnb-data-20261026T000000Z-remerged-r{index}', date)


def paginate(*pages):
    return [list(page) for page in pages]


class VerifiedReleaseTests(unittest.TestCase):
    def test_newest_complete_cnb_build_wins_over_manual_legacy_and_drafts(self):
        old = release('cnb-data-old', '2026-10-09T00:00:00Z')
        newest = release('cnb-data-new')
        api = Mock()
        api.request.return_value = [release('manual-latest'), release('data-latest'),
                                    release('cnb-data-partial', complete=False),
                                    release('cnb-data-draft', draft=True), old, newest]
        self.assertIs(downloader.select_release(api), newest)
        api.get_release.assert_not_called()

    def test_pagination_selects_by_publication_time(self):
        newest = release('cnb-data-new', '2026-10-11T00:00:00Z')
        api = Mock()
        api.request.side_effect = [[release('manual')] * 100, [newest]]
        self.assertIs(downloader.select_release(api), newest)
        self.assertEqual(api.request.call_count, 2)

    def test_exact_tag_never_falls_back(self):
        api = Mock()
        for value in (None, release('cnb-data-missing', draft=True), release('cnb-data-missing', complete=False)):
            api.get_release.return_value = value
            with self.assertRaises(ValueError): downloader.select_release(api, 'cnb-data-missing')
        api.request.assert_not_called()

    def test_untrusted_tag_rejected_before_network(self):
        api = Mock()
        for tag in ('data-latest', '../cnb-data-x', 'cnb-data-a/../../x', 'cnb-data-$(echo x)'):
            with self.assertRaises(ValueError): downloader.select_release(api, tag)
        api.get_release.assert_not_called()

    def test_legacy_fallback_only_without_complete_cnb_build(self):
        api = Mock()
        api.request.return_value = []
        legacy = release('data-latest')
        api.get_release.return_value = legacy
        self.assertIs(downloader.select_release(api), legacy)
        with self.assertRaises(ValueError): downloader.select_release(api, allow_legacy=False)

    def test_streaming_download_checks_size_and_hash(self):
        body = b'verified payload'
        class Response(io.BytesIO):
            def read(self, size=-1):
                if size <= 0: raise AssertionError('download must use bounded reads')
                return super().read(size)
        value = {'tag_name': 'cnb-data-test', 'assets': [{'name': 'manifest.json', 'id': 1,
                 'state': 'uploaded', 'size': len(body), 'digest': 'sha256:' + hashlib.sha256(body).hexdigest()}]}
        api = Mock(base='https://api.github.com/repos/Fatty911/test', headers={})
        with tempfile.TemporaryDirectory() as temp, patch.object(downloader.urllib.request, 'build_opener') as build:
            build.return_value.open.return_value = Response(body)
            downloader.download_assets(api, value, ['manifest.json'], Path(temp))
            self.assertEqual((Path(temp) / 'manifest.json').read_bytes(), body)
            self.assertEqual((Path(temp) / 'selected-release.txt').read_text().strip(), 'cnb-data-test')

    def test_truncated_download_does_not_replace_previous_payload(self):
        value = {'tag_name': 'cnb-data-test', 'assets': [{'name': 'manifest.json', 'id': 1,
                 'state': 'uploaded', 'size': 100}]}
        api = Mock(base='https://api.github.com/repos/Fatty911/test', headers={})
        with tempfile.TemporaryDirectory() as temp, patch.object(downloader.urllib.request, 'build_opener') as build:
            target = Path(temp) / 'manifest.json'
            target.write_bytes(b'previous')
            build.return_value.open.return_value = io.BytesIO(b'short')
            with self.assertRaises(ValueError): downloader.download_assets(api, value, ['manifest.json'], Path(temp))
            self.assertEqual(target.read_bytes(), b'previous')
            self.assertFalse((Path(temp) / 'manifest.json.partial').exists())

    def test_original_only_sees_past_more_than_forty_derived_builds(self):
        # GH#377 自然故障：原始 release 在列表索引 44，被本链自身产物挤出 --limit 40。
        ahead = [derived(index, f'2026-10-26T00:{index:02d}:00Z') for index in range(44)]
        raw = release(RAW_TAG, '2026-10-15T04:17:23Z')
        api = Mock()
        api.request.return_value = ahead + [raw]
        self.assertIs(downloader.select_release(api, original_only=True, allow_legacy=False), raw)
        self.assertIs(downloader.select_release(api), ahead[-1])

    def test_original_only_paginates_across_multiple_hundreds(self):
        raw = release(RAW_TAG, '2026-10-15T04:17:23Z')
        first = [derived(index) for index in range(100)]
        second = [derived(100 + index) for index in range(100)]
        third = [derived(200 + index) for index in range(7)] + [raw]
        api = Mock()
        api.request.side_effect = paginate(first, second, third)
        self.assertIs(downloader.select_release(api, original_only=True, allow_legacy=False), raw)
        self.assertEqual(api.request.call_count, 3)

    def test_original_only_prefers_original_despite_newer_derived_publication(self):
        raw = release(RAW_TAG, '2026-10-15T04:17:23Z')
        newer = derived(9, '2026-10-26T10:00:00Z')
        api = Mock()
        api.request.return_value = [newer, raw]
        self.assertIs(downloader.select_release(api, original_only=True, allow_legacy=False), raw)
        self.assertIs(downloader.select_release(api), newer)

    def test_original_only_rejects_draft_prerelease_and_incomplete_originals(self):
        good = release(RAW_TAG, '2026-10-15T04:17:23Z')
        api = Mock()
        api.request.return_value = [release('cnb-data-draft', draft=True),
                                    release('cnb-data-pre', prerelease=True),
                                    release('cnb-data-thin', complete=False),
                                    release('cnb-data-20261014T000000Z-cnb-x', '2026-10-14T00:00:00Z'),
                                    good]
        self.assertIs(downloader.select_release(api, original_only=True, allow_legacy=False), good)
        api.request.return_value = [release('cnb-data-draft', draft=True),
                                    release('cnb-data-pre', prerelease=True),
                                    release('cnb-data-thin', complete=False)]
        with self.assertRaises(ValueError):
            downloader.select_release(api, original_only=True, allow_legacy=False)

    def test_original_only_refuses_derived_only_without_legacy_or_self_feed(self):
        api = Mock()
        api.request.return_value = [derived(1), derived(2)]
        api.get_release.return_value = release('data-latest')
        for allow_legacy in (True, False):
            with self.assertRaises(ValueError):
                downloader.select_release(api, original_only=True, allow_legacy=allow_legacy)
        api.get_release.assert_not_called()

    def test_default_mode_still_selects_latest_complete_derived_build(self):
        raw = release(RAW_TAG, '2026-10-15T04:17:23Z')
        newest = derived(5, '2026-10-27T00:00:00Z')
        api = Mock()
        api.request.return_value = [raw, derived(4, '2026-10-26T00:00:00Z'), newest]
        self.assertIs(downloader.select_release(api), newest)
        api.get_release.assert_not_called()

    def test_original_only_explicit_tag_rejects_derived_and_accepts_exact_raw(self):
        api = Mock()
        api.get_release.return_value = derived(3)
        with self.assertRaises(ValueError):
            downloader.select_release(api, derived(3)['tag_name'], original_only=True)
        raw = release(RAW_TAG, '2026-10-15T04:17:23Z')
        api.get_release.return_value = raw
        self.assertIs(downloader.select_release(api, RAW_TAG, original_only=True), raw)
        api.request.assert_not_called()

    def test_cli_original_only_print_tag_emits_only_tag_without_download(self):
        raw = release(RAW_TAG, '2026-10-15T04:17:23Z')
        api = Mock()
        api.request.return_value = [derived(1, '2026-10-28T00:00:00Z'), raw]
        stdout = io.StringIO()
        with patch.object(downloader, 'GitHub', return_value=api), \
                patch.object(downloader, 'download_assets') as download, \
                contextlib.redirect_stdout(stdout):
            downloader.main(['--repo', 'Fatty911/test', '--no-legacy', '--original-only', '--print-tag'])
        self.assertEqual(stdout.getvalue(), RAW_TAG + '\n')
        download.assert_not_called()

    def test_cli_original_only_fails_nonzero_when_only_derived_builds_exist(self):
        # workflow 以 `if ! TAG=$(... --print-tag)` 依赖非零退出，不许退回派生构建或 data-latest。
        api = Mock()
        api.request.return_value = [derived(1, '2026-10-28T00:00:00Z')]
        stdout = io.StringIO()
        with patch.object(downloader, 'GitHub', return_value=api), \
                patch.object(downloader, 'download_assets') as download, \
                contextlib.redirect_stdout(stdout):
            with self.assertRaises(ValueError) as caught:
                downloader.main(['--repo', 'Fatty911/test', '--no-legacy', '--original-only', '--print-tag'])
        self.assertIn('no complete published original CNB build', str(caught.exception))
        self.assertEqual(stdout.getvalue(), '')
        download.assert_not_called()
        api.get_release.assert_not_called()

    def test_redirect_does_not_forward_token_to_asset_host(self):
        request = downloader.urllib.request.Request('https://api.github.com/repos/test', headers={'Authorization': 'Bearer secret'})
        redirected = downloader.SafeRedirect().redirect_request(request, None, 302, 'Found', {}, 'https://release-assets.githubusercontent.com/payload')
        self.assertIsNone(redirected.get_header('Authorization'))


if __name__ == '__main__':
    unittest.main()
