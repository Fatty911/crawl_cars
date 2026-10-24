"""Execute the real workflow guards and publication code without source requests."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow():
    return yaml.safe_load((ROOT / '.github/workflows/cnb-pages.yml').read_text(encoding='utf-8'))


def step_code(name):
    step = next(s for s in workflow()['jobs']['deploy']['steps'] if s.get('name') == name)
    return step['run'].split("python - <<'PY'\n", 1)[1].split('\nPY', 1)[0]


@pytest.mark.parametrize('event,ref,conclusion,branch,allowed', [
    ('workflow_dispatch', 'refs/heads/main', '', '', True),
    ('workflow_run', 'refs/heads/main', 'success', 'main', True),
    ('workflow_run', 'refs/heads/main', 'failure', 'main', False),
    ('workflow_run', 'refs/heads/main', 'cancelled', 'main', False),
    ('workflow_run', 'refs/heads/main', 'success', 'other', False),
    ('workflow_run', 'refs/tags/main', 'success', 'main', False),
    ('workflow_run', 'refs/heads/main', '', '', False),
])
def test_real_job_condition_rejects_failed_or_nondefault_upstreams(event, ref, conclusion, branch, allowed):
    spec = importlib.util.spec_from_file_location('ref_guard', ROOT / 'tests/test_workflow_pages_env_ref_guard.py')
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    expression = workflow()['jobs']['deploy']['if'].strip()[3:-2].strip()
    ctx = guard._Ctx({'github': {'ref': ref, 'event_name': event,
                     'event': {'workflow_run': {'conclusion': conclusion, 'head_branch': branch}}}}, fill='')
    assert guard.truthy(guard.evaluate(expression, ctx)) is allowed


@pytest.mark.parametrize('status,success,branch,domains,allowed', [
    (200, True, 'main', ['cars2.jiucai.eu.org'], True),
    (403, False, 'main', ['cars2.jiucai.eu.org'], False),
    (200, False, 'main', ['cars2.jiucai.eu.org'], False),
    (200, True, 'other', ['cars2.jiucai.eu.org'], False),
    (200, True, 'main', ['unrelated.example'], False),
])
def test_actual_upload_guard_refuses_wrong_or_unverified_target(tmp_path, status, success, branch, domains, allowed):
    response = {'success': success, 'result': {'name': 'crawl-cars', 'production_branch': branch, 'domains': domains}}
    stub = '''import os
from pathlib import Path
class Response:
    status_code = STATUS
    def json(self): return BODY
def get(url, headers, timeout):
    assert url == 'https://api.cloudflare.com/client/v4/accounts/fixture-account/pages/projects/crawl-cars'
    assert headers == {'Authorization': 'Bearer fixture-not-a-real-token'} and timeout == 30
    Path('actual-request-observed').write_text('one bounded metadata GET')
    return Response()
'''.replace('STATUS', str(status)).replace('BODY', repr(response))
    (tmp_path / 'requests.py').write_text(stub, encoding='utf-8')
    env = dict(os.environ, CLOUDFLARE_API_TOKEN='fixture-not-a-real-token', CLOUDFLARE_ACCOUNT_ID='fixture-account')
    result = subprocess.run([sys.executable, '-'], input=step_code('发布到既有crawl-cars生产项目'),
                            cwd=tmp_path, env=env, text=True, encoding='utf-8', capture_output=True, timeout=15)
    assert (tmp_path / 'actual-request-observed').exists()
    assert (result.returncode == 0) is allowed
    assert 'fixture-not-a-real-token' not in result.stdout


def test_real_publication_metadata_preserves_source_provenance_and_all_assets(tmp_path):
    data = tmp_path / 'cf-site/data'
    release = tmp_path / 'release'
    data.mkdir(parents=True)
    release.mkdir()
    raw = b'[{"id":1}]'
    (data / 'latest.json').write_bytes(raw)
    (tmp_path / 'cf-site/app.js').write_bytes(b'fixture frontend')
    manifest = {'rowCount': 1, 'provenance': {'codeCommit': 'original-data-commit'}, 'files': {
        'latestJson': 'data/latest.json', 'additionalDataAssets': [{
            'path': 'data/latest.json', 'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}]}}
    (data / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    original = b'{"original":"immutable source manifest"}'
    (release / 'manifest.json').write_bytes(original)
    (release / 'selected-release.txt').write_text('cnb-data-fixture-verified\n', encoding='utf-8')
    env = dict(os.environ, GITHUB_SHA='fixture-postprocess-commit', PYTHONPATH=str(ROOT))
    # The workflow inserts scripts/ relative to cwd. Supply only the unchanged real checker.
    (tmp_path / 'scripts').mkdir()
    (tmp_path / 'scripts/prepare_cnb_pages.py').write_bytes((ROOT / 'scripts/prepare_cnb_pages.py').read_bytes())
    result = subprocess.run([sys.executable, '-'], input=step_code('保留数据原件并无损封装Cloudflare发布面'),
                            cwd=tmp_path, env=env, text=True, encoding='utf-8', capture_output=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    actual = json.loads((data / 'manifest.json').read_bytes())
    assert actual['files'] == manifest['files'] and actual['provenance'] == manifest['provenance']
    assert (data / 'latest.json').read_bytes() == raw
    assert (release / 'manifest.json').read_bytes() == original
    assert actual['publication']['sourceManifestSha256'] == hashlib.sha256(original).hexdigest()
    assert actual['publication']['postprocessCodeCommit'] == 'fixture-postprocess-commit'
    assert actual['publication']['sourceVerifiedRelease'] == 'cnb-data-fixture-verified'
