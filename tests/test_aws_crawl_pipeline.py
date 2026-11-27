"""Bounded fixtures for AWS orchestration; none are production attestations."""

import base64
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts import aws_crawl_pipeline as pipeline
from scripts import aws_crawl_runtime as runtime
from scripts import aws_raw_bundle as raw
from scripts import aws_raw_platforms as mirrors


TAG = "aws-raw-20261106T010203Z"
PRODUCER = "a" * 40
STORAGE = {"ref": "main", "commit": "b" * 40}


def write_private(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)
    return pipeline.digest(path)


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        sources = pipeline.REQUIRED_SOURCES | {"scripts/transitive_dependency.py", "crawl_state/transitive_dependency.py"}
        for name in sources:
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# fixture source\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                        "commit", "-qm", "fixture"], cwd=self.repo, check=True)
        sha = pipeline.git(self.repo, "rev-parse", "HEAD").decode().strip()
        files = {name: pipeline.digest(self.repo / name) for name in sources}
        manifest = self.root / "sources.json"
        source_sha = write_private(manifest, {"producer_commit": sha, "files": files})
        target = self.root / "targets.json"
        target_sha = write_private(target, [{"id": "1", "name": "样本", "brand": "样本"}])
        self.plan = {
            "schema": 1, "plan_id": "fixture", "producer_commit": sha, "mode": "debug",
            "python": {"path": str(Path(sys.executable).resolve()), "sha256": pipeline.digest(Path(sys.executable).resolve())},
            "source_manifest": {"path": str(manifest), "sha256": source_sha},
            "targets": {"dongchedi": {"path": str(target), "sha256": target_sha, "row_limit": 30}},
            "network": {"probe_ip": "192.0.2.1", "probe_port": 22},
            "platforms": {"github": {"repo": "Fatty911/crawl_cars"},
                          "cnb": {"repo": "xuerui911-mirror/crawl_cars", "storage": STORAGE},
                          "gitlab": {"project": "xuerui911/crawl_cars", "storage": STORAGE}},
            "processing": {"commit": sha, "ref": "main", "workflow": pipeline.WORKFLOW,
                           "workflow_sha256": files[".github/workflows/" + pipeline.WORKFLOW],
                           "pages_base": "https://cars.jiucai.eu.org/"},
        }
        self.path = self.root / "plan.json"
        self.save()

    def save(self):
        write_private(self.path, self.plan)

    def test_dry_run_checks_real_git_bytes_without_any_effectors(self):
        with patch.object(pipeline, "assert_aws", side_effect=AssertionError("host effect")), \
             patch.object(raw, "publish_github", side_effect=AssertionError("remote effect")), \
             patch.object(pipeline, "collector_command", side_effect=AssertionError("collector effect")):
            result = pipeline.execute(self.path, repo=self.repo, state_root=self.root / "state")
        self.assertEqual(result["remote_writes"], 0)
        self.assertFalse((self.root / "state").exists())

    def test_unapproved_native_repo_and_redirecting_pages_base_are_rejected(self):
        for platform, key, value in (
            ("cnb", "repo", "Fatty911/crawl_cars"),
            ("gitlab", "project", "owner/cars"),
            ("processing", "pages_base", "https://fatty911.github.io/crawl_cars/"),
        ):
            with self.subTest(platform=platform):
                fields = self.plan["processing"] if platform == "processing" else self.plan["platforms"][platform]
                correct = fields[key]
                fields[key] = value
                self.save()
                with self.assertRaises(pipeline.PipelineError):
                    pipeline.validate_plan(self.path, self.repo)
                fields[key] = correct

    def test_optional_gitee_mirror_requires_the_exact_project_and_storage_commit(self):
        gitee = {"project": mirrors.GITEE_PROJECT, "storage": dict(STORAGE)}
        self.plan["platforms"]["gitee"] = gitee
        self.save()
        pipeline.validate_plan(self.path, self.repo)
        for key, invalid in (("project", "owner/other"), ("storage", {"ref": "main", "commit": "main"})):
            with self.subTest(key=key):
                original = gitee[key]
                gitee[key] = invalid
                self.save()
                with self.assertRaises(pipeline.PipelineError):
                    pipeline.validate_plan(self.path, self.repo)
                gitee[key] = original

    def test_source_modified_after_commit_is_rejected_even_with_updated_manifest(self):
        source = self.repo / "scripts/crawl_dongchedi.py"
        source.write_text("# changed after approval\n")
        manifest_path = Path(self.plan["source_manifest"]["path"])
        manifest = json.loads(manifest_path.read_bytes())
        manifest["files"]["scripts/crawl_dongchedi.py"] = pipeline.digest(source)
        self.plan["source_manifest"]["sha256"] = write_private(manifest_path, manifest)
        self.save()
        with self.assertRaisesRegex(pipeline.PipelineError, "dirty"):
            pipeline.validate_plan(self.path, self.repo)

    def test_omitted_transitive_script_is_not_accepted_as_source_closure(self):
        path = Path(self.plan["source_manifest"]["path"])
        manifest = json.loads(path.read_bytes())
        for name in ("scripts/transitive_dependency.py", "crawl_state/transitive_dependency.py", "crawl_state/registry.py"):
            with self.subTest(name=name):
                missing = {**manifest, "files": {key: sha for key, sha in manifest["files"].items() if key != name}}
                self.plan["source_manifest"]["sha256"] = write_private(path, missing)
                self.save()
                with self.assertRaisesRegex(pipeline.PipelineError, "omits"):
                    pipeline.validate_plan(self.path, self.repo)

    def test_target_drift_and_implicit_unbounded_debug_are_rejected(self):
        Path(self.plan["targets"]["dongchedi"]["path"]).write_text("[]")
        with self.assertRaisesRegex(pipeline.PipelineError, "reference changed"):
            pipeline.validate_plan(self.path, self.repo)
        self.plan["targets"]["dongchedi"]["sha256"] = write_private(
            Path(self.plan["targets"]["dongchedi"]["path"]), [{"id": "1", "name": "样本", "brand": "样本"}])
        self.plan["targets"]["dongchedi"]["row_limit"] = 0
        self.save()
        with self.assertRaisesRegex(pipeline.PipelineError, "debug"):
            pipeline.validate_plan(self.path, self.repo)

    def test_collectors_use_public_unit_entrypoints_and_resource_caps(self):
        command = pipeline.collector_command("dongchedi", {"row_limit": 10}, Path("/private/targets"),
                                             Path("/private/output"), self.plan["network"])
        self.assertIn("scripts.refresh_aws_dongchedi", command)
        self.assertNotIn("--worker", command)
        self.assertNotIn("scripts.merge_data", command)
        with patch.object(runtime.socket, "create_connection", return_value=MagicMock()), \
             patch.object(runtime.subprocess, "run") as run, \
             patch.dict(os.environ, {"AWS_CRAWL_UNIT_NAME": "crawl-cars-aws-collector"}):
            runtime.run_unit("scripts.refresh_aws_dongchedi", [], "192.0.2.1", 22, 240)
        arguments = run.call_args.args[0]
        for required in ["--unit=crawl-cars-aws-collector", "--property=IPAddressDeny=any",
                         "--property=IPAddressAllow=localhost", "--property=MemoryMax=2G", "--property=RuntimeMaxSec=240"]:
            self.assertIn(required, arguments)

    def test_bad_proxy_and_possible_direct_egress_fail_closed(self):
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.read.return_value = b'{"type":"LoadBalance","all":["DIRECT"],"emptyFallback":"DIRECT"}'
        with patch.object(runtime.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(ValueError):
                runtime.check_proxy()
        with patch.object(runtime.socket, "create_connection", return_value=MagicMock()):
            with self.assertRaisesRegex(ValueError, "direct egress"):
                runtime.check_blocked("192.0.2.1", 22)

    def test_mihomo_strategy_configuration_rejects_sticky_or_non_loopback_routes(self):
        config = {
            "mixed-port": 17890, "external-controller": "127.0.0.1:19090", "rules": ["MATCH,CRAWL"],
            "proxy-groups": [{"name": "CRAWL", "type": "load-balance", "strategy": "round-robin",
                              "empty-fallback": "REJECT"}],
        }
        runtime.validate_round_robin_config(config)
        for value in ("consistent-hashing", "sticky-sessions", None):
            other = copy.deepcopy(config)
            other["proxy-groups"][0]["strategy"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "round-robin"):
                runtime.validate_round_robin_config(other)
        for key, value in [("external-controller", "0.0.0.0:19090"), ("mixed-port", 7890), ("rules", ["MATCH,DIRECT"])]:
            other = dict(config, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                runtime.validate_round_robin_config(other)

    def test_production_is_rejected_on_non_aws_or_outside_the_owned_service(self):
        with patch.object(pipeline.os, "geteuid", return_value=0), patch.object(Path, "read_text", return_value="RackNerd"):
            with self.assertRaisesRegex(pipeline.PipelineError, "AWS EC2"):
                pipeline.assert_aws("aws-production")
        with patch.object(pipeline.os, "geteuid", return_value=0), \
             patch.object(Path, "read_text", side_effect=["Amazon EC2", "0::/user.slice/interactive"]), \
             patch.dict(os.environ, {"INVOCATION_ID": "fixture", "AWS_CRAWL_PRODUCTION_AUTHORIZED": "1"}):
            with self.assertRaisesRegex(pipeline.PipelineError, "systemd service"):
                pipeline.assert_aws("aws-production")

    def test_legacy_original_only_consumer_blocks_activation_preflight(self):
        workflow = self.repo / (".github/workflows/" + pipeline.WORKFLOW)
        workflow.write_text("# --original-only\n")
        subprocess.run(["git", "add", str(workflow)], cwd=self.repo, check=True)
        subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                        "commit", "-qm", "legacy fixture"], cwd=self.repo, check=True)
        sha = pipeline.git(self.repo, "rev-parse", "HEAD").decode().strip()
        self.plan["producer_commit"] = self.plan["processing"]["commit"] = sha
        manifest_path = Path(self.plan["source_manifest"]["path"])
        manifest = json.loads(manifest_path.read_bytes())
        manifest["producer_commit"] = sha
        manifest["files"][".github/workflows/" + pipeline.WORKFLOW] = pipeline.digest(workflow)
        self.plan["processing"]["workflow_sha256"] = pipeline.digest(workflow)
        self.plan["source_manifest"]["sha256"] = write_private(manifest_path, manifest)
        self.save()
        with self.assertRaisesRegex(pipeline.PipelineError, "activation remains blocked"):
            pipeline.validate_plan(self.path, self.repo)

    def test_missing_native_credential_stops_before_collecting_or_refreshing(self):
        self.plan["platforms"]["gitee"] = {"project": mirrors.GITEE_PROJECT, "storage": STORAGE}
        self.save()
        state_root = self.root / "state"

        def lookup(host, project):
            if host == "gitee.com":
                raise mirrors.PlatformError("credential detail must stay private")
            return "fixture"

        with patch.object(pipeline, "PLAN", self.path), patch.object(pipeline, "assert_aws"), \
             patch.object(mirrors, "credential", side_effect=lookup), \
             patch.object(pipeline, "refresh_priority_rankings") as refresh, \
             patch.object(pipeline, "collector_command") as collect, \
             patch.object(raw, "publish_github") as publish:
            with self.assertRaisesRegex(pipeline.PipelineError, "Gitee raw mirror credential unavailable"):
                pipeline.execute(self.path, apply=True, repo=self.repo, state_root=state_root)
        refresh.assert_not_called()
        collect.assert_not_called()
        publish.assert_not_called()
        self.assertFalse((state_root / "fixture/state.json").exists())

    def test_missing_dedicated_cnb_credential_is_distinguished_from_raw_access(self):
        self.plan["platforms"]["cnb"]["acceptance"] = {"ci_sha256": "c" * 64, "credential": "dedicated"}
        self.save()
        state_root = self.root / "state"
        with patch.object(pipeline, "PLAN", self.path), patch.object(pipeline, "assert_aws"), \
             patch.object(mirrors, "credential", return_value="fixture"), \
             patch.object(pipeline, "CNB_BUILD_CREDENTIAL", self.root / "missing-cnb.json"), \
             patch.object(pipeline, "refresh_priority_rankings") as refresh:
            with self.assertRaisesRegex(pipeline.PipelineError, "CNB build credential unavailable"):
                pipeline.execute(self.path, apply=True, repo=self.repo, state_root=state_root)
        refresh.assert_not_called()

    def test_mirror_failure_keeps_collected_bytes_and_cursor_pending_on_retry(self):
        self.plan["platforms"]["gitee"] = {"project": mirrors.GITEE_PROJECT, "storage": STORAGE}
        self.save()
        state_root = self.root / "state"
        collected = []
        original_run = subprocess.run

        def run(command, *args, **kwargs):
            if command[:3] == [sys.executable, "-m", "scripts.refresh_aws_dongchedi"]:
                output = Path(command[command.index("--output") + 1])
                output.mkdir(parents=True)
                (output / "dongchedi-source.json").write_text('[{"车系":"样本","车型名称":"样本车款"}]')
                collected.append(output)
                return subprocess.CompletedProcess(command, 0)
            return original_run(command, *args, **kwargs)

        with patch.object(pipeline, "PLAN", self.path), patch.object(pipeline, "assert_aws"), \
             patch.object(pipeline.subprocess, "run", side_effect=run), \
             patch.object(raw, "publish_github") as github, patch.object(mirrors, "credential", return_value="fixture"), \
             patch.object(mirrors, "Api"), \
             patch.object(mirrors, "mirror_cnb", side_effect=[mirrors.PlatformError("403 fixture"), {"verified": True}, {"verified": True}]), \
             patch.object(mirrors, "mirror_gitlab", return_value={"verified": True}), \
             patch.object(mirrors, "mirror_gitee", side_effect=[mirrors.PlatformError("Gitee pending"), {"verified": True}]), \
             patch.object(pipeline, "advance_processing", side_effect=pipeline.Pending("processing pending")) as process:
            with self.assertRaisesRegex(mirrors.PlatformError, "403"):
                pipeline.execute(self.path, apply=True, repo=self.repo, state_root=state_root)
            self.assertFalse(process.called)
            with self.assertRaisesRegex(mirrors.PlatformError, "Gitee pending"):
                pipeline.execute(self.path, apply=True, repo=self.repo, state_root=state_root)
            self.assertFalse(process.called)
            with self.assertRaises(pipeline.Pending):
                pipeline.execute(self.path, apply=True, repo=self.repo, state_root=state_root)
            self.assertEqual(len(collected), 1)
            self.assertTrue(github.call_args.kwargs["check_only"])
            self.assertFalse((state_root / "fixture/cursor.json").exists())

    def test_priority_refresh_does_not_change_a_pending_run_or_credit_unpublished_rows(self):
        today = pipeline.datetime.now(pipeline.timezone.utc).date().isoformat()
        catalog = self.root / "priority-catalog.json"
        rankings = self.root / "priority-rankings.json"
        targets = [{"id": str(i), "name": f"样本{i}", "brand": "样本"} for i in (1, 2)]
        digest = write_private(catalog, {"source": "dongchedi", "targets": [
            {"target": target, "trim_cost": 1} for target in targets
        ]})
        write_private(rankings, {"heat": {"observed_on": today, "ranks": {"1": 1, "2": 2}}})
        self.plan["targets"]["dongchedi"] = {"row_limit": 2, "priority": {
            "catalog_path": str(catalog), "catalog_sha256": digest, "rankings_path": str(rankings)
        }}
        self.save()
        state_root = self.root / "state"
        directory = state_root / "fixture"
        collected = []
        checks = []
        original_run = subprocess.run

        def run(command, *args, **kwargs):
            if command[:3] != [sys.executable, "-m", "scripts.refresh_aws_dongchedi"]:
                return original_run(command, *args, **kwargs)
            output = Path(command[command.index("--output") + 1])
            manifest = Path(command[command.index("--targets") + 1])
            collected.append(manifest.read_bytes())
            output.mkdir(parents=True)
            (output / "dongchedi-source.json").write_text('[{"车系":"样本1","车型名称":"样本甲","车系ID":"1"}]')
            return subprocess.CompletedProcess(command, 0)

        def advance(state, plan, actions, save):
            checks.append(copy.deepcopy(state["targets"]))
            if len(checks) == 1:
                raise pipeline.Pending("fixture processing pending")
            state.update(complete=True, dispatch={"run_id": 42})
            save()

        with patch.object(pipeline, "PLAN", self.path), patch.object(pipeline, "assert_aws"), \
             patch.object(pipeline.subprocess, "run", side_effect=run), \
             patch.object(raw, "publish_github"), patch.object(mirrors, "credential", return_value="fixture"), \
             patch.object(mirrors, "Api"), patch.object(mirrors, "mirror_cnb", return_value={"verified": True}), \
             patch.object(mirrors, "mirror_gitlab", return_value={"verified": True}), \
             patch.object(pipeline, "advance_processing", side_effect=advance):
            with self.assertRaises(pipeline.Pending):
                pipeline.execute(self.path, apply=True, repo=self.repo, state_root=state_root)
            self.assertFalse((directory / "priority-history.json").exists())
            write_private(rankings, {"heat": {"observed_on": today, "ranks": {"1": 2, "2": 1}}})
            result = pipeline.execute(self.path, apply=True, repo=self.repo, state_root=state_root)
            self.assertEqual(result["status"], "ACCEPTED")
            self.assertEqual(checks[0], checks[1])
            self.assertEqual(len(collected), 1)
            self.assertEqual(json.loads(collected[0]), targets)
            self.assertEqual(json.loads((directory / "priority-history.json").read_bytes()), {"dongchedi": {"1": today}})

    def test_atomic_state_failure_preserves_previous_receipt(self):
        state = self.root / "state.json"
        pipeline.atomic_json(state, {"phase": "pending"})
        before = state.read_bytes()
        with self.assertRaises(TypeError):
            pipeline.atomic_json(state, {"invalid": object()})
        self.assertEqual(state.read_bytes(), before)
        self.assertEqual(state.stat().st_mode & 0o077, 0)


class PriorityRuntimeTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.catalog = self.root / "catalog.json"
        self.rankings = self.root / "rankings.json"
        self.targets = [{"id": str(i), "name": f"样本{i}", "brand": "样本"} for i in (1, 2)]
        sha = write_private(self.catalog, {"source": "dongchedi", "targets": [
            {"target": target, "trim_cost": 1} for target in self.targets
        ]})
        write_private(self.rankings, {"heat": {"observed_on": "2026-11-12", "ranks": {"1": 1, "2": 2}}})
        self.plan = {"targets": {"dongchedi": {"row_limit": 2, "priority": {
            "catalog_path": str(self.catalog), "catalog_sha256": sha, "rankings_path": str(self.rankings)
        }}}}

    def test_fresh_targets_are_ranked_and_do_not_reselect_yesterdays_accepted_series(self):
        first = pipeline.plan_run_targets(self.plan, "20261112", {})
        self.assertEqual(json.loads(first["dongchedi"]["payload"]), self.targets)
        next_batch = pipeline.plan_run_targets(self.plan, "20261113", {"dongchedi": {"1": "2026-11-12"}})
        self.assertEqual(json.loads(next_batch["dongchedi"]["payload"]), [self.targets[1]])
        empty = pipeline.plan_run_targets(self.plan, "20261113", {"dongchedi": {"1": "2026-11-12", "2": "2026-11-12"}})
        self.assertEqual(empty, {})

    def test_pending_target_bytes_are_frozen_across_rank_refreshes(self):
        frozen = pipeline.plan_run_targets(self.plan, "20261112", {})
        first = frozen["dongchedi"]
        write_private(self.rankings, {"heat": {"observed_on": "2026-11-12", "ranks": {"1": 2, "2": 1}}})
        new_plan = pipeline.plan_run_targets(self.plan, "20261112", {})
        self.assertNotEqual(new_plan["dongchedi"]["sha256"], first["sha256"])
        self.assertEqual(pipeline.frozen_target_payload(first), first["payload"].encode())
        with self.assertRaisesRegex(pipeline.PipelineError, "frozen target"):
            pipeline.frozen_target_payload(dict(first, payload="[]"))

    def test_only_rows_with_an_observed_native_identity_enter_accepted_history(self):
        batch = pipeline.plan_run_targets(self.plan, "20261112", {})
        folder = self.root / "run" / "dongchedi"
        folder.mkdir(parents=True)
        source = folder / "dongchedi-source.json"
        source.write_text('[{"车系":"样本1","车型名称":"甲","车系ID":"1"},{"车系":"其他","车型名称":"乙","车系ID":"3"}]')
        state = {"complete": True, "period": "20261112", "targets": batch, "sources": {"dongchedi": raw.inspect_asset(source,"dongchedi")}}
        history = pipeline.accepted_priority_history(state, self.root / "run", {})
        self.assertEqual(history, {"dongchedi": {"1": "2026-11-12"}})
        self.assertEqual(pipeline.accepted_priority_history(state, self.root / "run", history), history)


class FakeActions:
    def __init__(self, *, post_error=False, conclusion="success", head=PRODUCER):
        self.calls = []
        self.post_error = post_error
        self.run = {"id": 42, "event": "workflow_dispatch", "head_sha": head, "head_branch": "main",
                    "path": ".github/workflows/" + pipeline.WORKFLOW, "status": "completed",
                    "conclusion": conclusion, "run_attempt": 1}

    def api(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "POST":
            if self.post_error:
                raise pipeline.Pending("response lost")
            return {"workflow_run_id": 42}
        if "/git/ref/" in path:
            return {"object": {"sha": PRODUCER}}
        if "/actions/workflows/" in path:
            return {"workflow_runs": [self.run] if self.post_error else []}
        return self.run


class ProcessingTests(unittest.TestCase):
    def setUp(self):
        self.state = {"tag": TAG, "raw_manifest_sha256": "c" * 64}
        self.plan = {"producer_commit": PRODUCER, "processing": {"commit": PRODUCER, "ref": "main",
                     "pages_base": "https://fatty911.github.io/crawl_cars/"}}
        self.saved = []

    def actions(self, **options):
        actions = FakeActions(**options)
        original = actions.api

        def api(method, path, body=None):
            if path.startswith("/releases/tags/"):
                actions.calls.append((method, path, body))
                run_id = 41 if path.endswith("-r41a1") else 42
                return self.release(self.manifest(run_id), run_id)
            return original(method, path, body)

        actions.api = api
        return actions

    def save(self):
        self.saved.append(copy.deepcopy(self.state))

    def page(self, url, bound):
        if url.endswith("index.html"):
            return b"<html>healthy</html>"
        payload = json.dumps([{"fixture_id": n} for n in range(27)]).encode()
        latest, filtered = "data/latest.0.json", "data/filtered.json"
        if url.endswith((latest, filtered)):
            return payload
        return self.manifest(42 if self.state.get("dispatch") else 41)

    def manifest(self, run_id):
        payload = json.dumps([{"fixture_id": n} for n in range(27)]).encode()
        latest, filtered = "data/latest.0.json", "data/filtered.json"
        asset = {"size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
        raw_tag = TAG if run_id == 42 else "aws-raw-20261105T010203Z"
        return json.dumps({"date": "20261106", "rowCount": 27, "filteredRowCount": 27, "files": {
            "latestJsonChunks": [dict(asset, path=latest, rowCount=27)],
            "filteredJson": filtered, "additionalDataAssets": [dict(asset, path=filtered)]}, "provenance": {
            "awsRawRelease": raw_tag, "awsRawManifestSha256": "c" * 64, "codeCommit": PRODUCER,
            "awsRawProducerCommit": PRODUCER, "workflowRunId": str(run_id), "workflowRunAttempt": "1",
            "inputRelease": "cnb-data-20261106-remerged-verified-r41a1"}}).encode()

    def test_lost_dispatch_response_is_durable_and_never_blindly_resent(self):
        actions = self.actions(post_error=True)
        for _ in range(2):
            with self.assertRaises(pipeline.Pending):
                pipeline.advance_processing(self.state, self.plan, actions, self.save, self.page)
        self.assertEqual(sum(method == "POST" for method, _, _ in actions.calls), 1)
        self.assertEqual(self.saved[0]["dispatch"]["status"], "pending")
        self.assertIn("after_ids", self.state["dispatch"])
        self.assertFalse(self.state.get("complete", False))

    def test_wrong_run_head_and_failed_run_never_advance(self):
        for actions in [self.actions(head="d" * 40), self.actions(conclusion="failure")]:
            self.state.pop("dispatch", None)
            with self.assertRaises(pipeline.PipelineError):
                pipeline.advance_processing(self.state, self.plan, actions, self.save, self.page)
            self.assertFalse(self.state.get("complete", False))

    def test_concurrent_matching_runs_are_recorded_without_guessing_a_dispatch(self):
        self.state["dispatch"] = {"status": "pending", "before_ids": []}
        actions = self.actions(post_error=True)
        original = actions.api

        def api(method, path, body=None):
            if "/actions/workflows/" in path:
                return {"workflow_runs": [actions.run, dict(actions.run, id=43)]}
            return original(method, path, body)

        actions.api = api
        with self.assertRaisesRegex(pipeline.Pending, "uncertain"):
            pipeline.advance_processing(self.state, self.plan, actions, self.save, lambda url, bound: b'{}')
        self.assertEqual(self.state["dispatch"]["candidate_ids"], [42, 43])
        self.assertNotIn("run_id", self.state["dispatch"])
        self.assertFalse(any(method == "POST" for method, _, _ in actions.calls))

    def test_lost_response_can_reconcile_only_with_exact_new_run_pages_provenance(self):
        self.state["dispatch"] = {"status": "pending", "before_ids": []}
        actions = self.actions(post_error=True)
        pipeline.advance_processing(self.state, self.plan, actions, self.save, self.page)
        self.assertTrue(self.state["dispatch"]["reconciled_from_pages_provenance"])
        self.assertTrue(self.state["complete"])
        self.assertFalse(any(method == "POST" for method, _, _ in actions.calls))

    def test_success_requires_raw_provenance_and_real_nonempty_health(self):
        pipeline.advance_processing(self.state, self.plan, self.actions(), self.save, self.page)
        self.assertTrue(self.state["complete"])
        self.assertEqual(self.state["dispatch"]["run_id"], 42)
        self.assertTrue(self.state["dispatch"]["pages_health_sha256"])

    def test_primary_acceptance_stays_pending_until_configured_native_followup_finishes(self):
        original = copy.deepcopy(self.state)
        for target in ({"gitlab": {"pages": {"url": "https://crawl-cars-5b0684.gitlab.io/"}}},
                       {"cnb": {"acceptance": {"ci_sha256": "d" * 64}}}):
            with self.subTest(target=target):
                self.state = copy.deepcopy(original)
                self.plan["platforms"] = target
                actions = self.actions()
                pipeline.advance_processing(self.state, self.plan, actions, self.save, self.page)
                self.assertEqual(self.state["dispatch"]["status"], "accepted")
                self.assertFalse(self.state.get("complete", False))
                calls = list(actions.calls)
                pipeline.advance_processing(self.state, self.plan, actions, self.save, self.page)
                self.assertEqual(actions.calls, calls)

    def test_current_manifest_with_stale_page_data_never_advances(self):
        for asset in ("data/latest.0.json", "data/filtered.json"):
            self.state.pop("dispatch", None)
            def stale(url, bound):
                value = self.page(url, bound)
                return b" " + value[1:] if url.endswith(asset) else value
            with self.subTest(asset=asset), self.assertRaisesRegex(pipeline.Pending, "Pages data asset"):
                pipeline.advance_processing(self.state, self.plan, self.actions(), self.save, stale)
            self.assertFalse(self.state.get("complete", False))

    def release(self, payload, run_id):
        return {
            "tag_name": f"cnb-data-20261106-remerged-verified-r{run_id}a1",
            "draft": False, "prerelease": False, "immutable": True,
            "assets": [
                {"name": "manifest.json", "state": "uploaded", "size": len(payload),
                 "digest": "sha256:" + hashlib.sha256(payload).hexdigest()},
                {"name": "verified-site.zip", "state": "uploaded", "size": 1234,
                 "digest": "sha256:" + "f" * 64},
            ],
        }

    def pages_cycle(self, *, bad_digest=False, different_input=False):
        baseline_tag = "cnb-data-20261106-remerged-verified-r41a1"
        actions = FakeActions()
        original = actions.api
        base = self.plan["processing"]["pages_base"] + "data/manifest.json"
        output = json.loads(self.manifest(42))
        output["date"] = "20261106"
        output["provenance"]["inputRelease"] = baseline_tag if not different_input else "another-release"
        preceding = copy.deepcopy(output)
        preceding["provenance"].update(workflowRunId="41", awsRawRelease="aws-raw-20261105T010203Z")
        old, new = (json.dumps(x).encode() for x in (preceding, output))

        def api(method, path, body=None):
            if path.startswith("/releases/tags/"):
                actions.calls.append((method, path, body))
                if path.endswith(baseline_tag):
                    return self.release(b'wrong baseline' if bad_digest else old, 41)
                return self.release(new, 42)
            return original(method, path, body)

        def page(url, bound):
            if url == base:
                return new if any(method == "POST" for method, _, _ in actions.calls) else old
            return self.page(url, bound)

        actions.api = api
        return actions, page, baseline_tag

    def test_split_pages_requires_exact_bytes_for_all_published_downloads(self):
        base = self.plan["processing"]["pages_base"]
        files = {
            "latestJson": "data/latest.json",
            "filteredJson": "data/filtered.json",
            "latestCsv": "data/latest.csv",
            "filteredCsv": "data/filtered.csv",
        }
        latest_part = "data/latest.0.json"
        filtered_part = "data/filtered.0.json"
        payloads = {name: name.encode() for name in (*files.values(), latest_part, filtered_part)}

        def descriptor(path):
            return {"path": path, "size": len(payloads[path]), "sha256": hashlib.sha256(payloads[path]).hexdigest()}

        manifest = {"files": {
            **files,
            "latestJsonChunks": [descriptor(latest_part)],
            "filteredJsonChunks": [descriptor(filtered_part)],
            "additionalDataAssets": [descriptor(path) for path in files.values()],
        }}

        def page(url, bound):
            payload = payloads[url.removeprefix(base)]
            self.assertEqual(len(payload), bound)
            return payload

        self.assertEqual(set(pipeline.verify_page_data(manifest, base, page)), set(payloads))
        payloads[files["latestCsv"]] = b"x" * len(payloads[files["latestCsv"]])
        with self.assertRaisesRegex(pipeline.Pending, "data/latest.csv"):
            pipeline.verify_page_data(manifest, base, page)

    def test_dispatch_pins_archive_matching_the_live_pages_bytes(self):
        actions, page, baseline_tag = self.pages_cycle()
        pipeline.advance_processing(self.state, self.plan, actions, self.save, page)
        post = next(body for method, _, body in actions.calls if method == "POST")
        self.assertEqual(post["inputs"], {"aws_raw_release": TAG, "release_tag": baseline_tag})
        self.assertEqual(self.saved[0]["dispatch"]["baseline_tag"], baseline_tag)
        self.assertEqual(self.state["dispatch"]["processed_release"], "cnb-data-20261106-remerged-verified-r42a1")

    def test_mismatched_live_baseline_never_dispatches(self):
        actions, page, _ = self.pages_cycle(bad_digest=True)
        with self.assertRaisesRegex(pipeline.Pending, "manifest bytes"):
            pipeline.advance_processing(self.state, self.plan, actions, self.save, page)
        self.assertFalse(any(method == "POST" for method, _, _ in actions.calls))

    def test_live_output_with_different_input_never_advances(self):
        actions, page, _ = self.pages_cycle(different_input=True)
        with self.assertRaisesRegex(pipeline.Pending, "input baseline"):
            pipeline.advance_processing(self.state, self.plan, actions, self.save, page)
        self.assertFalse(self.state.get("complete", False))

    def test_stale_pages_or_health_failure_stays_pending(self):
        for getter in [lambda url, bound: b'{}', lambda url, bound: (_ for _ in ()).throw(pipeline.Pending("unreachable"))]:
            self.state.pop("dispatch", None)
            with self.assertRaises(pipeline.Pending):
                pipeline.advance_processing(self.state, self.plan, self.actions(), self.save, getter)
            self.assertFalse(self.state.get("complete", False))


class PublicPagesMirrorTests(unittest.TestCase):
    def test_mirror_completion_requires_both_codeberg_sites_and_exact_release(self):
        source = "cnb-data-20261112-remerged-verified-r42a1"
        state = {"tag": TAG, "raw_manifest_sha256": "c" * 64, "dispatch": {
            "status": "accepted", "processed_release": source, "pages_manifest_sha256": "d" * 64,
            "row_count": 1, "filtered_row_count": 1,
        }}
        manifest = {"rowCount": 1, "filteredRowCount": 1, "publication": {
            "platform": "codeberg-pages", "sourceVerifiedRelease": source,
            "sourceManifestSha256": "d" * 64,
        }, "provenance": {"awsRawRelease": TAG, "awsRawProducerCommit": PRODUCER,
                         "awsRawManifestSha256": "c" * 64}}
        _, _, sites = pipeline.PAGE_MIRRORS["codeberg"]
        current = {sites[0]: manifest, sites[1]: {**manifest, "publication": {}}}
        calls, saves = [], []

        def get_page(url, maximum):
            calls.append(url)
            if url in sites:
                return b"ok"
            return json.dumps(current[url.removesuffix("data/manifest.json")]).encode()

        def advance():
            pipeline.advance_public_page_mirrors(state, ["codeberg"], PRODUCER,
                                                lambda: saves.append(copy.deepcopy(state)), get_page)

        with patch.object(pipeline, "verify_page_data", return_value={"data": "ok"}):
            with self.assertRaisesRegex(pipeline.Pending, "exact processed batch"):
                advance()
            self.assertEqual(set(state["public_page_mirrors"]), {sites[0]})
            current[sites[1]] = manifest
            advance()
            self.assertEqual(set(state["public_page_mirrors"]), set(sites))
            self.assertEqual(calls.count(sites[0] + "data/manifest.json"), 1)
            self.assertEqual(len(saves), 2)


class GitLabPagesTests(unittest.TestCase):
    def setUp(self):
        self.commit = "b" * 40
        self.ci = "d" * 64
        self.url = "https://crawl-cars-5b0684.gitlab.io/"
        self.config = {"project": "xuerui911/crawl_cars", "storage": {"ref": "main", "commit": self.commit},
                       "pages": {"url": self.url, "ci_sha256": self.ci}}
        self.payload = b'[{"fixture":true}]'
        entry = {"size": len(self.payload), "sha256": hashlib.sha256(self.payload).hexdigest()}
        self.manifest = json.dumps({"rowCount": 1, "filteredRowCount": 1, "files": {
            "latestJsonChunks": [dict(entry, path="data/latest.0.json", rowCount=1)],
            "filteredJson": "data/filtered.json",
            "additionalDataAssets": [dict(entry, path="data/filtered.json")],
        }}).encode()
        self.state = {"tag": TAG, "raw_manifest_sha256": "c" * 64, "dispatch": {
            "status": "accepted", "processed_release": "cnb-data-20261106-remerged-verified-r42a1",
            "pages_manifest_sha256": hashlib.sha256(self.manifest).hexdigest()
        }}
        self.variables = {"CARS_PROCESSED_RELEASE": self.state["dispatch"]["processed_release"],
                          "CARS_AWS_RAW_RELEASE": TAG, "CARS_AWS_PRODUCER_COMMIT": PRODUCER,
                          "CARS_AWS_RAW_MANIFEST_SHA256": "c" * 64}
        self.calls = []
        self.saved = []
        self.post_fails = False
        self.api = MagicMock(request=self.request)

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "POST":
            if self.post_fails:
                raise mirrors.PlatformError("lost GitLab response")
            return {"id": 51}
        if "/repository/branches/" in path:
            return {"commit": {"id": self.commit}}
        if "/repository/files/" in path:
            return {"content_sha256": self.ci, "commit_id": self.commit}
        if path.endswith("/pages"):
            return {"url": self.url.rstrip("/")}
        if "/pipelines?" in path:
            return [{"id": 51}] if any(call[0] == "POST" for call in self.calls) else []
        if path.endswith("/variables"):
            return [{"key": key, "value": value} for key, value in self.variables.items()]
        if path.endswith("/pipelines/51"):
            return {"id": 51, "ref": "main", "sha": self.commit, "source": "api", "status": "success"}
        raise AssertionError(path)

    def get(self, url, bound):
        if url.endswith("data/manifest.json"):
            return self.manifest
        if url.endswith("index.html"):
            return b"<html>healthy</html>"
        return self.payload

    def save(self):
        self.saved.append(copy.deepcopy(self.state))

    def test_gitlab_dispatch_uses_exact_archive_and_verifies_private_assets(self):
        pipeline.advance_gitlab_pages(self.state,self.config,PRODUCER,self.api,self.save,self.get)
        post=next(call for call in self.calls if call[0]=="POST")
        self.assertEqual(post[2]["variables"], [{"key":key,"value":value} for key,value in self.variables.items()])
        self.assertEqual(self.saved[0]["gitlab_pages"]["status"],"pending")
        self.assertEqual(self.state["gitlab_pages"]["status"],"accepted")
        self.assertEqual(len(self.state["gitlab_pages"]["verified_data_assets"]),2)

    def test_lost_response_reconciles_with_exact_pipeline_variables_and_no_second_post(self):
        self.post_fails=True
        with self.assertRaisesRegex(pipeline.Pending,"dispatch response"):
            pipeline.advance_gitlab_pages(self.state,self.config,PRODUCER,self.api,self.save,self.get)
        pipeline.advance_gitlab_pages(self.state,self.config,PRODUCER,self.api,self.save,self.get)
        self.assertEqual(sum(call[0]=="POST" for call in self.calls),1)
        self.assertTrue(self.state["gitlab_pages"]["reconciled"])

    def test_gitlab_bearer_never_goes_to_another_origin(self):
        with patch.object(pipeline.urllib.request,"build_opener") as opener:
            read = pipeline.private_gitlab_page_reader(self.url,"fixture-token")
            with self.assertRaisesRegex(pipeline.PipelineError,"cannot leave"):
                read("https://other.gitlab.io/data/manifest.json",1024)
            opener.return_value.open.assert_not_called()

    def test_ci_drift_or_wrong_pages_manifest_cannot_complete(self):
        wrong=copy.deepcopy(self.config)
        wrong["pages"]["ci_sha256"]="e"*64
        with self.assertRaisesRegex(pipeline.PipelineError,"CI"):
            pipeline.advance_gitlab_pages(self.state,wrong,PRODUCER,self.api,self.save,self.get)
        self.assertFalse(any(call[0]=="POST" for call in self.calls))
        with self.assertRaisesRegex(pipeline.Pending,"manifest"):
            pipeline.advance_gitlab_pages(self.state,self.config,PRODUCER,self.api,self.save,lambda url,bound:b'{}')
        self.assertEqual(self.state["gitlab_pages"]["status"],"pending")


class CnbBuildCredentialTests(unittest.TestCase):
    def test_explicit_build_credential_does_not_read_raw_release_token(self):
        config = {"repo": "xuerui911-mirror/crawl_cars", "acceptance": {"credential": "dedicated"}}
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "build-credential.json"
            with patch.object(pipeline, "CNB_BUILD_CREDENTIAL", path), \
                 patch.object(mirrors, "credential", side_effect=AssertionError("raw credential fallback")):
                with self.assertRaises((OSError, pipeline.PipelineError)):
                    pipeline.cnb_acceptance_credential(config)
                write_private(path, {"token": "fixture-build-token"})
                self.assertEqual(pipeline.cnb_acceptance_credential(config), "fixture-build-token")
                write_private(path, {"token": "fixture" + chr(10) + "invalid"})
                with self.assertRaisesRegex(pipeline.PipelineError, "invalid"):
                    pipeline.cnb_acceptance_credential(config)
                write_private(path, {"token": "fixture-build-token"})
                path.chmod(0o644)
                with self.assertRaises(pipeline.PipelineError):
                    pipeline.cnb_acceptance_credential(config)

    def test_existing_plan_uses_its_configured_repository_credential(self):
        config = {"repo": "xuerui911-mirror/crawl_cars", "acceptance": {}}
        with patch.object(mirrors, "credential", return_value="fixture-existing") as store:
            self.assertEqual(pipeline.cnb_acceptance_credential(config), "fixture-existing")
        store.assert_called_once_with("cnb.cool", config["repo"])


class CnbAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.repo = "xuerui911-mirror/crawl_cars"
        self.ci = b"fixture"
        self.config = {"repo": self.repo, "storage": STORAGE,
                       "acceptance": {"ci_sha256": hashlib.sha256(self.ci).hexdigest()}}
        self.state = {"tag": TAG, "raw_manifest_sha256": "c" * 64, "dispatch": {
            "status": "accepted", "processed_release": "cnb-data-20261106-remerged-verified-r42a1",
        }}
        self.saved = []
        self.posts = []
        self.rows = []
        self.history_denied = False
        self.lost_response = False
        self.build_status = "success"
        self.stage_statuses = ["success", "success"]
        self.api = MagicMock(request=self.request)

    def save(self):
        self.saved.append(copy.deepcopy(self.state))

    def request(self, method, path, body=None):
        if method == "POST" and path.endswith("/build/start"):
            self.posts.append(body)
            assert self.saved[-1]["cnb_acceptance"]["request"] == body
            self.rows.append({"title": body["title"], "sha": STORAGE["commit"], "slug": self.repo,
                              "event": "api_trigger", "sourceRef": "refs/heads/main", "sn": "cnb-fixture-1"})
            if self.lost_response:
                raise mirrors.PlatformError("lost CNB response")
            return {"success": True, "sn": "cnb-fixture-1"}
        if path.endswith("/git/branches/main"):
            return {"commit": {"sha": STORAGE["commit"]}}
        if path.endswith("/git/contents/.cnb.yml?ref=" + STORAGE["commit"]):
            return {"encoding": "base64", "content": base64.b64encode(self.ci).decode()}
        if "/build/logs?" in path:
            if self.history_denied:
                raise mirrors.PlatformError("platform API HTTP 403")
            return {"data": self.rows, "total": len(self.rows)}
        if path.endswith("/build/status/cnb-fixture-1"):
            stages = [{"name": name, "status": status}
                      for name, status in zip(pipeline.CNB_ACCEPTANCE_STAGES, self.stage_statuses)]
            return {"status": self.build_status,
                    "pipelinesStatus": {"fixture": {"status": self.build_status, "stages": stages}}}
        raise AssertionError(path)

    def advance(self):
        pipeline.advance_cnb_acceptance(self.state, self.config, PRODUCER, self.api, self.save)

    def test_cnb_workflow_declares_the_stages_required_by_aws(self):
        import yaml

        workflow_path = Path(__file__).resolve().parents[1] / ".cnb.yml"
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        build, = workflow["main"]["api_trigger"]
        raw_stage, processed_stage = build["stages"]
        self.assertEqual(
            (raw_stage["name"], processed_stage["name"]),
            pipeline.CNB_ACCEPTANCE_STAGES,
        )
        self.assertIn('--tag "$AWS_PROCESSED_RELEASE"', processed_stage["script"])
        self.assertIn("--require-immutable", processed_stage["script"])
        self.assertIn("AWS_RAW_MANIFEST_SHA256", processed_stage["script"])

    def test_exact_archive_is_dispatched_once_and_both_stages_verified(self):
        self.advance()
        self.advance()
        self.assertEqual(len(self.posts), 1)
        request = self.posts[0]
        self.assertEqual(request["sha"], STORAGE["commit"])
        self.assertEqual(request["env"], {"AWS_RAW_RELEASE": TAG, "AWS_RAW_PRODUCER_COMMIT": PRODUCER,
                                          "AWS_PROCESSED_RELEASE": self.state["dispatch"]["processed_release"],
                                          "AWS_RAW_MANIFEST_SHA256": self.state["raw_manifest_sha256"]})
        self.assertEqual(self.state["cnb_acceptance"]["status"], "accepted")

    def test_lost_response_reconciles_without_redispatch(self):
        self.lost_response = True
        with self.assertRaisesRegex(pipeline.Pending, "response unavailable"):
            self.advance()
        self.advance()
        self.assertEqual(len(self.posts), 1)
        self.assertTrue(self.state["cnb_acceptance"]["reconciled"])

    def test_mismatched_config_and_denied_history_stop_before_post(self):
        original = self.ci
        self.ci = b"legacy source crawl"
        with self.assertRaisesRegex(pipeline.PipelineError, "approved data-only"):
            self.advance()
        self.ci = original
        self.history_denied = True
        with self.assertRaisesRegex(mirrors.PlatformError, "403"):
            self.advance()
        self.assertEqual(self.posts, [])
        self.assertEqual(self.saved, [])

    def test_ambiguous_history_and_skipped_stage_do_not_advance(self):
        self.build_status = "pending"
        with self.assertRaisesRegex(pipeline.Pending, "still pending"):
            self.advance()
        self.rows.append(dict(self.rows[0], sn="cnb-other"))
        with self.assertRaisesRegex(pipeline.Pending, "identity remains uncertain"):
            self.advance()
        self.rows.pop()
        self.build_status = "success"
        self.stage_statuses[1] = "skipped"
        with self.assertRaisesRegex(pipeline.PipelineError, "both approved"):
            self.advance()
        self.assertEqual(len(self.posts), 1)
        self.assertEqual(self.state["cnb_acceptance"]["status"], "pending")


class FakePlatform:
    def __init__(self, bundle, kind):
        self.files = {p.name: p.read_bytes() for p in bundle.iterdir()}
        self.kind = kind
        self.release = None
        self.calls = []
        self.uploads = {}
        self.pending_name = None

    def request(self, method, path, body=None, **kwargs):
        self.calls.append((method, path, copy.deepcopy(body)))
        if "/branches/main" in path:
            return {"commit": {"sha" if self.kind == "cnb" else "id": STORAGE["commit"]}}
        if "/git/tags/" in path or "/repository/tags/" in path:
            return {"commit": {"sha" if self.kind == "cnb" else "id": STORAGE["commit"]}} if self.release else None
        if method == "GET" and ("/releases/tags/" in path or path.endswith("/releases/" + TAG)):
            return copy.deepcopy(self.release)
        if method == "POST" and path.endswith("/releases"):
            if self.kind == "cnb":
                self.release = dict(body, id="release-1", assets=None)
            else:
                self.release = dict(body, assets={"links": body["assets"]["links"]})
            return copy.deepcopy(self.release)
        if path.endswith("asset-upload-url"):
            self.pending_name = body["asset_name"]
            assert body["overwrite"] is False
            return {"upload_url": "https://objects.example/upload?opaque=fixture", "verify_url":
                    "https://api.cnb.cool/owner/cars/-/releases/release-1/asset-upload-confirmation/opaque/file"}
        if "asset-upload-confirmation" in path:
            if self.release["assets"] is None:
                self.release["assets"] = []
            self.release["assets"].append({"name": self.pending_name, "size": len(self.files[self.pending_name])})
            return None
        if method == "PATCH":
            self.release.update(body)
            return None
        if "/releases/download/" in path:
            return self.files[path.rsplit("/", 1)[1]]
        if "/uploads?" in path:
            return [{"id": key, "filename": value[0], "size": len(value[1])} for key, value in self.uploads.items()]
        if "/uploads/" in path:
            return self.uploads[int(path.rsplit("/", 1)[1])][1]
        raise AssertionError((method, path))

    def put_signed(self, url, path):
        self.calls.append(("PUT_UNSIGNED", "object-storage", None))
        assert path.read_bytes() == self.files[self.pending_name]

    def upload_gitlab(self, endpoint, path, filename):
        self.calls.append(("UPLOAD", endpoint, filename))
        key = len(self.uploads) + 1
        self.uploads[key] = (filename, path.read_bytes())
        return {"id": key}


class FakeGitee:
    def __init__(self):
        self.base = "/api/v5/repos/" + mirrors.GITEE_PROJECT
        self.release_path = self.base + "/releases/tags/" + TAG
        self.attachment_path = self.base + "/releases/17/attach_files"
        self.tag_commit = None
        self.release = None
        self.attachments = {}
        self.writes = []
        self.lose_response = set()
        self.hide_attachments = False

    def request(self, method, path, body=None, **kwargs):
        if method == "GET":
            if path == self.base:
                return {"full_name": mirrors.GITEE_PROJECT}
            if path == self.base + "/branches/main":
                return {"commit": {"sha": STORAGE["commit"]}}
            if path == self.base + "/commits/" + TAG:
                return {"sha": self.tag_commit} if self.tag_commit else None
            if path == self.release_path:
                return copy.deepcopy(self.release)
            if path == self.attachment_path:
                return [] if self.hide_attachments else [
                    {"id": asset_id, "name": name, "size": len(data)}
                    for asset_id, (name, data) in self.attachments.items()
                ]
            for asset_id, (_, data) in self.attachments.items():
                if path == f"{self.attachment_path}/{asset_id}/download" and kwargs["binary"]:
                    return data
        elif method == "POST" and path == self.base + "/releases":
            self.writes.append("create")
            self.release = {**body, "id": 17}
            self.tag_commit = body["target_commitish"]
            if "create" in self.lose_response:
                raise mirrors.PlatformError("create response lost")
            return copy.deepcopy(self.release)
        elif method == "PATCH" and path == self.base + "/releases/17":
            self.writes.append("publish")
            self.release.update(body)
            return copy.deepcopy(self.release)
        raise AssertionError((method, path))

    def upload_attachment(self, endpoint, path, filename):
        assert endpoint == self.attachment_path
        self.writes.append(filename)
        self.attachments[len(self.attachments) + 1] = (filename, path.read_bytes())
        if filename in self.lose_response:
            raise mirrors.PlatformError("upload response lost")


class MirrorTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        source = self.root / "source.json"
        source.write_text('[{"车系":"真实结构样本","车型名称":"样本车款"}]', encoding="utf-8")
        self.bundle = self.root / "bundle"
        raw.pack(self.bundle, TAG, PRODUCER, {"dongchedi": source})

    def call(self, api, journal, check_only=False):
        function = mirrors.mirror_cnb if api.kind == "cnb" else mirrors.mirror_gitlab
        return function(api, "owner/cars", self.bundle, TAG, PRODUCER, STORAGE, journal, lambda: None, check_only=check_only)

    def test_cnb_owned_draft_and_gitlab_complete_link_transaction_are_immutable_on_retry(self):
        for kind in ["cnb", "gitlab"]:
            api = FakePlatform(self.bundle, kind)
            receipt = self.call(api, {})
            self.assertTrue(receipt["verified"])
            self.assertEqual(receipt["binding"]["producer_commit"], PRODUCER)
            self.assertEqual(receipt["binding"]["storage_commit"], STORAGE["commit"])
            api.calls.clear()
            self.call(api, {}, check_only=True)
            self.assertTrue(all(method == "GET" for method, _, _ in api.calls))

    def test_published_partial_releases_are_rejected_without_repairs(self):
        for kind in ["cnb", "gitlab"]:
            api = FakePlatform(self.bundle, kind)
            self.call(api, {})
            if kind == "cnb":
                api.release["assets"].pop()
            else:
                api.release["assets"]["links"].pop()
            api.calls.clear()
            with self.assertRaises(mirrors.PlatformError):
                self.call(api, {})
            self.assertTrue(all(method == "GET" for method, _, _ in api.calls))

    def test_cnb_resumes_confirmed_assets_after_visibility_delay_without_uploading_again(self):
        api = FakePlatform(self.bundle, "cnb")
        original = api.request
        visible = False

        def request(method, path, body=None, **kwargs):
            result = original(method, path, body, **kwargs)
            if method == "GET" and "/releases/tags/" in path and result and result["draft"] and not visible:
                result["assets"] = []
            return result

        api.request = request
        journal = {}
        with patch.object(mirrors.time, "sleep") as sleep:
            with self.assertRaisesRegex(mirrors.PlatformError, "confirmed assets are not yet visible"):
                self.call(api, journal)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [2, 4, 8, 16, 30])
        self.assertTrue(api.release["draft"])
        self.assertEqual(set(journal["confirmed_assets"]), set(api.files))
        self.assertEqual(sum(method == "PUT_UNSIGNED" for method, _, _ in api.calls), len(api.files))
        self.assertFalse(any(method == "PATCH" for method, _, _ in api.calls))

        api.calls.clear()
        visible = True
        self.assertTrue(self.call(api, journal)["verified"])
        self.assertFalse(any(method in {"POST", "PUT_UNSIGNED"} for method, _, _ in api.calls))
        patch_index = next(i for i, call in enumerate(api.calls) if call[0] == "PATCH")
        self.assertEqual(sum("/releases/download/" in path for _, path, _ in api.calls[:patch_index]), 2 * len(api.files))

    def test_cnb_lost_create_response_resumes_only_the_owned_draft(self):
        api = FakePlatform(self.bundle, "cnb")
        original = api.request
        failed = []

        def request(method, path, body=None, **kwargs):
            result = original(method, path, body, **kwargs)
            if method == "POST" and path.endswith("/releases") and not failed:
                failed.append(True)
                raise mirrors.PlatformError("create response lost")
            return result

        api.request = request
        journal = {}
        with self.assertRaisesRegex(mirrors.PlatformError, "response lost"):
            self.call(api, journal)
        self.assertTrue(self.call(api, journal)["verified"])
        self.assertEqual(sum(method == "POST" and path.endswith("/releases") for method, path, _ in api.calls), 1)
        api.release["draft"] = True
        api.calls.clear()
        with self.assertRaisesRegex(mirrors.PlatformError, "owned"):
            self.call(api, {})
        self.assertTrue(all(method == "GET" for method, _, _ in api.calls))

    def test_release_creation_waits_for_visibility_after_lost_response(self):
        for kind in ("cnb", "gitlab"):
            with self.subTest(platform=kind):
                api = FakePlatform(self.bundle, kind)
                original = api.request
                pending = False
                visible = False

                def request(method, path, body=None, **kwargs):
                    if method == "GET" and "/releases" in path and pending and not visible:
                        return None
                    result = original(method, path, body, **kwargs)
                    if method == "POST" and path.endswith("/releases") and not pending:
                        raise mirrors.PlatformError("create response lost")
                    return result

                api.request = request
                journal = {}
                with self.assertRaisesRegex(mirrors.PlatformError, "response lost"):
                    self.call(api, journal)
                pending = True
                api.calls.clear()
                with self.assertRaisesRegex(mirrors.PlatformError, "awaiting visible release"):
                    self.call(api, journal)
                self.assertTrue(all(method == "GET" for method, _, _ in api.calls))
                visible = True
                self.assertTrue(self.call(api, journal)["verified"])
                self.assertFalse(any(method == "POST" and path.endswith("/releases")
                                     for method, path, _ in api.calls))

    def test_gitlab_uncertain_upload_is_not_sent_again(self):
        api = FakePlatform(self.bundle, "gitlab")
        binding, _ = mirrors.bundle_identity(self.bundle, TAG, PRODUCER, STORAGE)
        journal = {"binding": binding, "pending_upload": raw.MANIFEST, "uploads": {}}
        with self.assertRaisesRegex(mirrors.PlatformError, "missing/ambiguous"):
            self.call(api, journal)
        self.assertFalse(any(method == "UPLOAD" for method, _, _ in api.calls))

    def test_check_only_missing_release_has_no_remote_writes(self):
        for kind in ["cnb", "gitlab"]:
            api = FakePlatform(self.bundle, kind)
            with self.assertRaises(mirrors.PlatformError):
                self.call(api, {}, check_only=True)
            self.assertTrue(all(method == "GET" for method, _, _ in api.calls))

    def gitee(self, api, journal, *, check_only=False, save=None):
        return mirrors.mirror_gitee(api, mirrors.GITEE_PROJECT, self.bundle, TAG, PRODUCER, STORAGE,
                                    journal, save or (lambda: None), check_only=check_only)

    def test_gitee_download_does_not_forward_credentials_or_follow_second_redirect(self):
        api = mirrors.Api(mirrors.GITEE, "synthetic-token")
        path = "/api/v5/repos/" + mirrors.GITEE_PROJECT + "/releases/17/attach_files/7/download"
        redirect = "https://assets.example.org/asset?signature=synthetic"

        def response(status, body=b"", location=None):
            handle = MagicMock()
            result = handle.__enter__.return_value
            result.status_code = status
            result.is_redirect = location is not None
            result.headers = {"Location": location} if location else {}
            result.iter_content.return_value = [body]
            return handle

        with patch.object(mirrors.requests, "get", side_effect=[mirrors.requests.ConnectionError(), response(200, b"ok")]) as get:
            self.assertEqual(api.request("GET", path, binary=True), b"ok")
            self.assertEqual(get.call_count, 2)
        with patch.object(mirrors.requests, "get", side_effect=[response(302, location=redirect), response(200, b"ok")]) as get:
            self.assertEqual(api.request("GET", path, binary=True), b"ok")
            first, second = get.call_args_list
            self.assertEqual(first.args[0], mirrors.GITEE + path)
            self.assertIn("Authorization", first.kwargs["headers"])
            self.assertEqual(second.args[0], redirect)
            self.assertNotIn("headers", second.kwargs)
            self.assertIsNotNone(second.kwargs["auth"])
            self.assertFalse(first.kwargs["allow_redirects"])
            self.assertFalse(second.kwargs["allow_redirects"])
        with patch.object(mirrors.requests, "get", side_effect=[response(302, location=redirect), response(302, location=redirect)]) as get:
            with self.assertRaisesRegex(mirrors.PlatformError, "download HTTP 302"):
                api.request("GET", path, binary=True)
            self.assertEqual(get.call_count, 2)
        with patch.object(mirrors.requests, "get", return_value=response(302, location=redirect)) as get:
            with self.assertRaisesRegex(mirrors.PlatformError, "read HTTP 302"):
                api.request("GET", path)
            get.assert_called_once()
        with patch.object(mirrors.requests, "get") as get:
            with self.assertRaisesRegex(mirrors.PlatformError, "escaped"):
                api.request("GET", "/api/v5/repos/" + mirrors.GITEE_PROJECT + "/../other")
            get.assert_not_called()

    def test_gitee_attachment_uses_native_multipart_without_redirecting_or_retrying(self):
        api = mirrors.Api(mirrors.GITEE, "synthetic-token")
        name = raw.MANIFEST
        path = self.bundle / name
        endpoint = "/api/v5/repos/" + mirrors.GITEE_PROJECT + "/releases/17/attach_files"
        with patch.object(mirrors.requests, "post") as post:
            def upload(url, **kwargs):
                self.assertEqual(url, mirrors.GITEE + endpoint)
                self.assertFalse(kwargs["allow_redirects"])
                self.assertEqual(kwargs["timeout"], (15, 70))
                filename, source, media_type = kwargs["files"]["file"]
                self.assertEqual((filename, media_type), (name, "application/json"))
                self.assertEqual(source.read(), path.read_bytes())
                self.assertTrue(kwargs["stream"])
                response = MagicMock()
                active = response.__enter__.return_value
                active.status_code = 201
                active.iter_content.return_value = [json.dumps({"id": 7, "name": name, "size": path.stat().st_size}).encode()]
                return response
            post.side_effect = upload
            self.assertEqual(api.upload_attachment(endpoint, path, name)["id"], 7)
            post.assert_called_once()
            post.reset_mock()
            post.side_effect = mirrors.requests.ConnectionError("sensitive transport detail")
            with self.assertRaisesRegex(mirrors.PlatformError, "transaction remains pending") as failure:
                api.upload_attachment(endpoint, path, name)
            self.assertNotIn("sensitive", str(failure.exception))
            post.assert_called_once()
            post.reset_mock()
            with self.assertRaisesRegex(mirrors.PlatformError, "Gitee attachment path"):
                api.upload_attachment("//example.invalid/upload", path, name)
            post.assert_not_called()

    def test_gitee_lost_create_and_upload_responses_reconcile_without_duplicate_writes(self):
        api = FakeGitee()
        journal = {}
        first_asset = sorted(path.name for path in self.bundle.iterdir())[0]
        api.lose_response = {"create", first_asset}
        saved = []
        save = lambda: saved.append(copy.deepcopy(journal))

        with self.assertRaisesRegex(mirrors.PlatformError, "create response lost"):
            self.gitee(api, journal, save=save)
        self.assertEqual(saved[-1]["binding"]["tag"], TAG)
        with self.assertRaisesRegex(mirrors.PlatformError, "upload response lost"):
            self.gitee(api, journal, save=save)
        self.assertEqual(saved[-1]["pending_upload"], first_asset)

        api.hide_attachments = True
        with self.assertRaisesRegex(mirrors.PlatformError, "awaiting visible attachment"):
            self.gitee(api, journal, save=save)
        self.assertEqual(api.writes, ["create", first_asset])
        api.hide_attachments = False
        self.assertTrue(self.gitee(api, journal, save=save)["verified"])
        self.assertEqual(api.writes, ["create", *sorted(path.name for path in self.bundle.iterdir()), "publish"])
        self.assertTrue(self.gitee(api, {}, check_only=True,
                                   save=MagicMock(side_effect=AssertionError("unexpected save")))["verified"])
        self.assertEqual(api.writes.count("publish"), 1)

    def test_gitee_rejects_foreign_pending_release_wrong_tag_and_corrupted_bytes(self):
        api = FakeGitee()
        with self.assertRaisesRegex(mirrors.PlatformError, "absent"):
            self.gitee(api, {}, check_only=True)
        api.lose_response = {"create"}
        journal = {}
        with self.assertRaisesRegex(mirrors.PlatformError, "response lost"):
            self.gitee(api, journal)
        with self.assertRaisesRegex(mirrors.PlatformError, "owned"):
            self.gitee(api, {})
        api.tag_commit = PRODUCER
        with self.assertRaisesRegex(mirrors.PlatformError, "another storage commit"):
            self.gitee(api, journal)
        self.assertEqual(api.writes, ["create"])

        api.tag_commit = STORAGE["commit"]
        self.assertTrue(self.gitee(api, journal)["verified"])
        name, data = api.attachments[1]
        api.attachments[1] = (name, bytes([data[0] ^ 1]) + data[1:])
        writes = list(api.writes)
        with self.assertRaisesRegex(mirrors.PlatformError, "SHA-256"):
            self.gitee(api, journal)
        self.assertEqual(api.writes, writes)

    def test_gitee_rejects_oversized_attachment_before_remote_effects(self):
        api = MagicMock()
        with patch.object(mirrors, "GITEE_MAX_ATTACHMENT_BYTES", 1):
            with self.assertRaisesRegex(mirrors.PlatformError, "per-file limit"):
                self.gitee(api, {})
        self.assertEqual(api.mock_calls, [])

    def test_credential_reference_uses_url_line_git_helper_without_secret_argv(self):
        store = self.root / "synthetic-credentials"
        store.write_text("https://fixture:synthetic-secret@gitlab.com/owner/cars.git\n")
        store.chmod(0o600)
        original_run = subprocess.run
        with patch.object(mirrors, "CREDENTIAL_STORE", store), patch.object(mirrors.subprocess, "run", wraps=original_run) as run:
            self.assertEqual(mirrors.credential("gitlab.com", "owner/cars"), "synthetic-secret")
            self.assertEqual(mirrors.credential("gitlab.com", "owner/cars.git"), "synthetic-secret")
            with self.assertRaises(mirrors.PlatformError):
                mirrors.credential("gitlab.com", "owner/another-repo")
        self.assertIn("credential-store", run.call_args.args[0])
        self.assertNotIn("synthetic-secret", " ".join(run.call_args.args[0]))

    def test_signed_object_upload_does_not_forward_api_authentication(self):
        api = mirrors.Api(mirrors.CNB, "synthetic-API-token")
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.status = 200
        with patch.object(mirrors.urllib.request, "build_opener", return_value=opener):
            api.put_signed("https://objects.example/upload?signature=synthetic", self.bundle / raw.MANIFEST)
        request = opener.open.call_args.args[0]
        self.assertIsNone(request.get_header("Authorization"))
        self.assertIsNone(request.get_header("Private-token"))
        self.assertEqual(request.get_header("Content-type"), "application/octet-stream")


if __name__ == "__main__":
    unittest.main()
