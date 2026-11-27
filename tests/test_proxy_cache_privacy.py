"""Offline, real-Git regressions: runtime auth caches cannot become public artifacts."""
from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts/validate_storage_policy.py"
CACHE_PATHS = {"proxies.json", "data/proxies.json"}


class ProxyCachePrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="proxy-cache-guard-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env.update({
            "HOME": str(self.root / "empty-home"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_COUNT": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "/bin/false",
            "GIT_ALLOW_PROTOCOL": "",
            "GIT_AUTHOR_NAME": "Privacy Guard Fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Privacy Guard Fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        })
        (self.root / "empty-home").mkdir()
        self.write(".gitignore", (ROOT / ".gitignore").read_bytes())
        self.write("scripts/validate_storage_policy.py", GATE.read_bytes())
        self.git("init", "-q")

    def write(self, path, content=b'{"fixture": true}\n'):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target

    def git(self, *args):
        return subprocess.run(
            ["git", "-c", "credential.helper=", "-c", "core.hooksPath=/dev/null",
             "-c", "commit.gpgsign=false", *args],
            cwd=self.root, env=self.env, capture_output=True, check=True,
        )

    def guard(self, *, head=False, full=False, env=None):
        args = [] if full else ["--proxy-cache-only"]
        if head:
            args.append("--check-head")
        return subprocess.run(
            [sys.executable, str(self.root / "scripts/validate_storage_policy.py"), *args],
            cwd=self.root, env=self.env if env is None else env,
            capture_output=True, text=True,
        )

    def assert_allowed(self, **kwargs):
        self.assertEqual(0, self.guard(**kwargs).returncode, "clean synthetic Git state rejected")

    def assert_blocked(self, **kwargs):
        result = self.guard(**kwargs)
        self.assertNotEqual(0, result.returncode, "runtime cache publication was allowed")
        self.assertTrue("runtime proxy cache" in result.stderr)

    def test_normal_stage_all_ignores_both_caches_and_keeps_public_state(self):
        for path in CACHE_PATHS:
            self.write(path)
        self.write("data/progress.json")
        self.write("config/proxies.json.example")
        self.git("add", "-A")
        tracked = set(self.git("ls-files", "-z").stdout.decode().split("\0"))
        self.assertFalse(tracked & CACHE_PATHS)
        self.assertTrue({"data/progress.json", "config/proxies.json.example"} <= tracked)
        self.assert_allowed()

    def test_data_wide_normal_stage_does_not_collect_cache(self):
        self.write("data/proxies.json")
        self.write("data/progress.json")
        self.git("add", "data")
        self.assert_allowed()
        self.assertTrue(b"data/progress.json\0" in self.git("ls-files", "-z").stdout)

    def test_force_stage_known_path_or_whole_directory_is_blocked(self):
        for args in [("-f", "proxies.json"), ("-f", "data/proxies.json"),
                     ("-f", "data"), ("-f", ".")]:
            with self.subTest(stage=args):
                for path in CACHE_PATHS:
                    self.write(path)
                self.git("add", *args)
                self.assert_blocked()
                self.git("rm", "-r", "-f", "--cached", "--ignore-unmatch", ".")

    def test_an_existing_tracked_cache_is_not_protected_by_ignore(self):
        self.write("data/proxies.json")
        self.git("add", "-f", "data/proxies.json")
        self.git("commit", "-q", "-m", "synthetic legacy cache")
        self.write("data/proxies.json", b'{"fixture": false}\n')
        self.git("add", "-A")
        self.assert_blocked()
        self.assert_blocked(head=True)

    def test_staged_removal_allows_repair_but_old_head_cannot_be_pushed(self):
        cache = self.write("data/proxies.json")
        self.git("add", "-f", "data/proxies.json")
        self.git("commit", "-q", "-m", "synthetic legacy cache")
        self.git("rm", "--cached", "data/proxies.json")
        self.assert_allowed()  # The clean replacement commit may be created.
        self.assert_blocked(head=True)  # A staged deletion alone cannot sanitize HEAD.
        self.git("commit", "-q", "-m", "remove synthetic runtime cache")
        self.assert_allowed(head=True)
        self.assertTrue(cache.is_file(), "guard must not delete private runtime copies")
        self.git("add", "-A")
        self.assert_allowed(head=True)

    def test_symlink_cache_is_blocked_without_dereferencing(self):
        path = self.root / "data/proxies.json"
        path.parent.mkdir(parents=True)
        path.symlink_to("nonexistent-fixture-target")
        self.git("add", "-f", "data/proxies.json")
        self.assert_blocked()

    def test_nul_safe_index_with_unrelated_unusual_name(self):
        self.write("ordinary\nfilename.txt")
        self.git("add", "-A")
        self.assert_allowed()
        self.write("proxies.json", b"\x00\xff")
        self.git("add", "-f", "proxies.json")
        self.assert_blocked()  # Filename only: never decode/cache/log credential bytes.

    def test_missing_git_dependency_fails_closed(self):
        env = dict(self.env, PATH="")
        result = self.guard(env=env)
        self.assertNotEqual(0, result.returncode)
        self.assertTrue("cannot inspect Git index" in result.stderr)

    def test_missing_head_fails_closed_for_publication_check(self):
        result = self.guard(head=True)
        self.assertNotEqual(0, result.returncode)
        self.assertTrue("cannot inspect Git HEAD" in result.stderr)

    def test_full_storage_gate_includes_runtime_cache_rule(self):
        module = ast.parse(GATE.read_text(encoding="utf-8"))
        allowed = next(ast.literal_eval(node.value) for node in module.body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "ALLOWED_DATA"
                               for t in node.targets))
        self.assertFalse(CACHE_PATHS & allowed)
        for path in allowed:
            self.write(path)
        self.git("add", "-f", "--", *sorted(allowed))
        self.assert_allowed(full=True)
        self.write("proxies.json")
        self.git("add", "-f", "proxies.json")
        self.assert_blocked(full=True)


    def test_replace_refs_cannot_hide_a_cache_in_the_published_head(self):
        self.git("commit", "--allow-empty", "-q", "-m", "synthetic clean commit")
        clean = self.git("rev-parse", "HEAD").stdout.decode().strip()
        self.write("data/proxies.json")
        self.git("add", "-f", "data/proxies.json")
        self.git("commit", "-q", "-m", "synthetic cache commit")
        bad = self.git("rev-parse", "HEAD").stdout.decode().strip()
        self.git("replace", bad, clean)
        self.git("rm", "--cached", "data/proxies.json")
        self.assert_allowed()  # Clean replacement index is legitimate for a repair.
        self.assert_blocked(head=True)  # Raw commit tree still contains the cache.

    def test_git_fsmonitor_hook_is_not_executed_by_guard(self):
        self.write("ordinary.txt")
        self.git("add", "ordinary.txt")
        marker = self.root / "fsmonitor-executed"
        hook = self.write("fixture-fsmonitor", (
            '#!/bin/sh\nprintf ran > "' + str(marker) + '"\nprintf "fixture-token\\0"\n'
        ).encode())
        hook.chmod(0o700)
        self.git("config", "core.fsmonitor", str(hook))
        self.git("ls-files")  # Positive control: the harmless hook really is configured.
        self.assertTrue(marker.exists())
        marker.unlink()
        self.assert_allowed()
        self.assertFalse(marker.exists(), "guard executed a configured repository hook")

    def test_git_timeout_fails_closed_with_bounded_subprocess(self):
        spec = importlib.util.spec_from_file_location("fixture_storage_policy", GATE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with mock.patch.object(module.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 15)) as run:
            with self.assertRaisesRegex(SystemExit, "cannot inspect Git index"):
                module.validate_proxy_cache(root=self.root)
        self.assertTrue(0 < run.call_args.kwargs["timeout"] <= 30)
        self.assertTrue("--no-replace-objects" in run.call_args.args[0])
        self.assertTrue("core.fsmonitor=false" in run.call_args.args[0])
        self.assertEqual("1", run.call_args.kwargs["env"]["GIT_NO_LAZY_FETCH"])
        self.assertEqual("", run.call_args.kwargs["env"]["GIT_ALLOW_PROTOCOL"])

    def test_failure_handler_cannot_publish_cache_left_in_index(self):
        self.git("commit", "--allow-empty", "-q", "-m", "synthetic clean baseline")
        cache = self.write("data/proxies.json")
        self.git("add", "-f", "data/proxies.json")
        self.assert_blocked()
        old_head = self.git("rev-parse", "HEAD").stdout
        old_index = self.git("ls-files", "--stage", "-z").stdout
        cnb_text = (ROOT / ".cnb.yml").read_text(encoding="utf-8")
        self.assertNotIn("HEAD:refs/heads/diag", cnb_text)
        self.assertNotIn("git add diag", cnb_text)
        self.assertNotIn("data/proxies.json", cnb_text)
        fail_block = cnb_text.split("failStages:", 1)[1].split("\n  api_trigger:", 1)[0]
        self.assertIn("_fail_context_.md", fail_block)
        self.assertIn("scripts/check_delivery_artifacts.py", fail_block)
        script_lines = []
        in_script = False
        script_indent = 0
        for line in fail_block.splitlines():
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if re.match(r"script:\s*(?:&\S+\s*)?\|", stripped):
                in_script = True
                script_indent = indent
                continue
            if in_script:
                if stripped and indent <= script_indent:
                    in_script = False
                elif stripped:
                    script_lines.append(stripped)
        script_body = "\n".join(script_lines)
        for forbidden in ("git commit", "git push", "git add"):
            self.assertNotIn(forbidden, script_body)
        self.assertEqual(old_head, self.git("rev-parse", "HEAD").stdout)
        self.assertEqual(old_index, self.git("ls-files", "--stage", "-z").stdout)
        self.assertTrue(cache.is_file())


    def test_obsolete_historical_snapshots_cannot_be_refilled_into_public_git(self):
        module = ast.parse(GATE.read_text(encoding="utf-8"))
        allowed = next(ast.literal_eval(node.value) for node in module.body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "ALLOWED_DATA"
                               for t in node.targets))
        for path in allowed:
            self.write(path)
        self.git("add", "-f", "--", *sorted(allowed))
        stale = ["data/dongchedi_20260302.json", "data/filtered_cars_20260622.csv",
                 "data/filtered_cars_20260622.json", "data/merged_20260622.csv",
                 "data/merged_20260622.json"]
        self.assertFalse(set(stale) & allowed)
        for path in stale:
            with self.subTest(snapshot=path):
                self.write(path)
                self.git("add", "-f", path)
                result = self.guard(full=True)
                self.assertNotEqual(0, result.returncode)
                self.assertTrue("tracked data allowlist drift" in result.stderr)
                self.git("rm", "--cached", path)


class ProxyCacheWiringTests(unittest.TestCase):
    def test_all_three_cnb_pushbacks_check_index_then_rebased_head(self):
        cnb_text = (ROOT / ".cnb.yml").read_text(encoding="utf-8")
        for removed in ("回推增量状态", "回推报价数据", "git add -f data/proxies.json",
                        "HEAD:refs/heads/diag", "git add diag"):
            self.assertNotIn(removed, cnb_text)
        api_block = cnb_text.split("\n  api_trigger:", 1)[1].split("\n  pull_request:", 1)[0]
        self.assertIn("验收AWS原始镜像", api_block)
        self.assertIn("验收已处理 Pages 制品", api_block)
        for forbidden in ("git commit", "git push", "git add", "git rebase"):
            self.assertNotIn(forbidden, api_block)

    def test_npc_finalize_checks_raw_index_and_head_before_publishing(self):
        cnb_text = (ROOT / ".cnb.yml").read_text(encoding="utf-8")
        self.assertNotIn("cars-npc-guard.py finalize", cnb_text)
        fail_block = cnb_text.split("failStages:", 1)[1].split("\n  api_trigger:", 1)[0]
        self.assertNotIn("git push ", fail_block)

    def test_existing_storage_ci_runs_fixture_tests_and_head_guard(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        storage = workflow.split("  storage-policy:", 1)[1]
        self.assertTrue('test_proxy_cache_privacy.py' in storage)
        self.assertTrue('validate_storage_policy.py --proxy-cache-only --check-head' in storage)


if __name__ == "__main__":
    unittest.main()
