"""Exercise immutable and interrupted AWS raw release publication."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import aws_raw_bundle as raw


TAG = "aws-raw-20261105T023300Z"
COMMIT = "a" * 40
REPO = "owner/crawl_cars"


class RawReleaseTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        root = Path(scratch.name)
        source = root / "source.json"
        source.write_text('[{"车系":"样本车系","车型名称":"样本车款"}]', encoding="utf-8")
        self.bundle = root / "bundle"
        raw.pack(self.bundle, TAG, COMMIT, {"dongchedi": source})
        self.release = {
            "tagName": TAG,
            "targetCommitish": COMMIT,
            "isDraft": False,
            "isPrerelease": True,
            "url": f"https://github.com/{REPO}/releases/tag/{TAG}",
            "assets": [
                {"name": p.name, "state": "uploaded", "size": p.stat().st_size,
                 "digest": "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in self.bundle.iterdir()
            ],
        }
        self.ref = json.dumps({"object": {"sha": COMMIT, "type": "commit"}})

    def test_already_published_retry_only_reads(self):
        with patch.object(raw, "gh", side_effect=[self.ref, json.dumps(self.release), self.ref]) as gh:
            result = raw.publish_github(self.bundle, TAG, REPO)
        self.assertEqual(result["tag"], TAG)
        self.assertEqual([call.args[:2] for call in gh.call_args_list],
                         [("api", "--hostname"), ("release", "view"), ("api", "--hostname")])

    def test_receiver_check_only_accepts_complete_published_release_without_writes(self):
        with patch.object(raw, "gh", side_effect=[self.ref, json.dumps(self.release), self.ref]) as gh:
            result = raw.publish_github(self.bundle, TAG, REPO, check_only=True)
        self.assertEqual(result["tag"], TAG)
        self.assertEqual([call.args[:2] for call in gh.call_args_list],
                         [("api", "--hostname"), ("release", "view"), ("api", "--hostname")])

    def test_receiver_check_only_rejects_draft_without_publishing(self):
        draft = dict(self.release, isDraft=True)
        with patch.object(raw, "gh", side_effect=[self.ref, json.dumps(draft)]) as gh:
            with self.assertRaisesRegex(ValueError, "still a draft"):
                raw.publish_github(self.bundle, TAG, REPO, check_only=True)
        self.assertTrue(all(call.args[:2] in [("api", "--hostname"), ("release", "view")]
                            for call in gh.call_args_list))

    def test_receiver_check_only_rejects_missing_asset_without_uploading(self):
        incomplete = dict(self.release, assets=self.release["assets"][:-1])
        with patch.object(raw, "gh", side_effect=[self.ref, json.dumps(incomplete)]) as gh:
            with self.assertRaisesRegex(ValueError, "incomplete"):
                raw.publish_github(self.bundle, TAG, REPO, check_only=True)
        self.assertEqual(gh.call_count, 2)

    def test_incomplete_draft_uploads_only_missing_assets(self):
        draft = dict(self.release, isDraft=True, assets=[self.release["assets"][0]])
        verified_draft = dict(self.release, isDraft=True)
        with patch.object(raw, "gh", side_effect=[
            None, json.dumps(draft), "", json.dumps(verified_draft), None, "", self.ref,
            "", json.dumps(self.release), self.ref,
        ]) as gh:
            raw.publish_github(self.bundle, TAG, REPO)
        commands = [call.args for call in gh.call_args_list]
        upload = next(args for args in commands if args[:2] == ("release", "upload"))
        self.assertEqual(upload[-1], str(self.bundle / self.release["assets"][1]["name"]))
        self.assertNotIn("--clobber", upload)
        self.assertEqual([args[:2] for args in commands].count(("release", "edit")), 1)

    def test_new_release_verifies_created_tag_before_draft_and_again_before_publication(self):
        draft = dict(self.release, isDraft=True, assets=[])
        complete_draft = dict(self.release, isDraft=True)
        with patch.object(raw, "gh", side_effect=[
            None, None, "", self.ref, "", json.dumps(draft), "",
            json.dumps(complete_draft), self.ref, "", json.dumps(self.release), self.ref,
        ]) as gh:
            result = raw.publish_github(self.bundle, TAG, REPO)
        self.assertEqual(result["tag"], TAG)
        commands = [call.args for call in gh.call_args_list]
        self.assertIn(f"ref=refs/tags/{TAG}", commands[2])
        self.assertIn(f"sha={COMMIT}", commands[2])
        self.assertIn("--verify-tag", commands[4])
        self.assertEqual(commands[3], commands[8])
        self.assertEqual(commands[9][:2], ("release", "edit"))
        self.assertEqual(gh.call_args_list[6].kwargs["timeout"], 3600)

    def test_tag_move_during_upload_never_exposes_draft(self):
        draft = dict(self.release, isDraft=True, assets=[])
        complete_draft = dict(self.release, isDraft=True)
        moved = json.dumps({"object": {"sha": "b" * 40, "type": "commit"}})
        with patch.object(raw, "gh", side_effect=[
            self.ref, json.dumps(draft), "", json.dumps(complete_draft), moved,
        ]) as gh:
            with self.assertRaisesRegex(ValueError, "different producer commit"):
                raw.publish_github(self.bundle, TAG, REPO)
        self.assertFalse(any(call.args[:2] == ("release", "edit") for call in gh.call_args_list))

    def test_missing_release_in_check_only_never_creates_tag(self):
        with patch.object(raw, "gh", side_effect=[None, None]) as gh:
            with self.assertRaisesRegex(ValueError, "raw release is missing"):
                raw.publish_github(self.bundle, TAG, REPO, check_only=True)
        self.assertEqual(gh.call_count, 2)

    def test_rejects_draft_with_different_asset_digest(self):
        self.release["isDraft"] = True
        self.release["assets"][0]["digest"] = "sha256:" + "0" * 64
        with patch.object(raw, "gh", side_effect=[None, json.dumps(self.release)]) as gh:
            with self.assertRaisesRegex(ValueError, "asset does not match"):
                raw.publish_github(self.bundle, TAG, REPO)
        self.assertEqual(gh.call_count, 2)

    def test_different_tag_commit_fails_before_release_write(self):
        other = json.dumps({"object": {"sha": "b" * 40, "type": "commit"}})
        with patch.object(raw, "gh", return_value=other) as gh:
            with self.assertRaisesRegex(ValueError, "different producer commit"):
                raw.publish_github(self.bundle, TAG, REPO)
        self.assertEqual(gh.call_count, 1)
