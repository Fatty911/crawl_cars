"""Machine gates for the CNB NPC repair, review, commit and bounded retry chain."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

REPORTS = {"_fail_context_.md", "_fix_report_.md", "_test_after_fix_.txt",
           "_review_result_.md", "_repair_diff_.patch", "_stage_context_.env"}
REPOSITORY = "xuerui911-mirror/crawl_cars"
SAFETY_SCRIPTS = {"scripts/check_npc_free_quota.py", "scripts/finalize_npc_repair.py"}


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def file_state(root):
    result = {}
    tracked = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root)
    for name in set(tracked.decode("utf-8").split("\0")) - {""}:
        if name in REPORTS or name.startswith("diag/"):
            continue
        path = root / name
        if path.is_symlink():
            result[name] = {"link": os.readlink(path)}
        elif path.is_file():
            result[name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "mode": path.stat().st_mode & 0o777}
    return result


def allowed_path(name):
    path = Path(name)
    if name in SAFETY_SCRIPTS or path.name == "AGENTS.md" or path.name.startswith("test_") or ".test." in path.name:
        return False
    if path.parts[0] in {"tests", "ai_tools", ".git"} or name.startswith("docs/data/"):
        return False
    if path.name in {"opencode.json", "oh-my-openagent.json"}:
        return False
    if name == ".cnb.yml":
        return True
    return path.parts[0] in {"scripts", "dongchedi", "docs", "config"} and path.suffix in {
        ".py", ".js", ".sh", ".html", ".css", ".json", ".yml", ".yaml", ".svg"
    }


def snapshot(root, state_dir):
    state_dir.mkdir(parents=True, exist_ok=False)
    files = file_state(root)
    protected = [name for name in files if name in SAFETY_SCRIPTS or name.startswith(("tests/", "ai_tools/")) or Path(name).name == "AGENTS.md"]
    for name in protected:
        source = root / name
        if source.is_file() and not source.is_symlink():
            backup = state_dir / "protected" / name
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, backup)
    baseline = {"head": git(root, "rev-parse", "HEAD"), "files": files,
                "safety_chains": safety_chains(root)}
    (state_dir / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
    for name in ("_review_result_.md", "_fix_report_.md", "_test_after_fix_.txt", "_repair_diff_.patch"):
        (root / name).unlink(missing_ok=True)
    print("protected backup and working-tree snapshot complete")


def safety_chains(root):
    import yaml
    workflow = yaml.safe_load((root / ".cnb.yml").read_text(encoding="utf-8"))
    main = workflow.get("main", {})
    return {event: [pipeline.get("failStages") for pipeline in main.get(event, [])]
            for event in ("api_trigger", "crontab: 5 8 1,16 * *")}


def changed_files(root, baseline):
    if git(root, "rev-parse", "HEAD") != baseline["head"]:
        raise ValueError("NPC must not create commits or change HEAD")
    if safety_chains(root) != baseline["safety_chains"]:
        raise ValueError("NPC must not modify failStages safety chains")
    current = file_state(root)
    names = sorted(name for name in set(current) | set(baseline["files"])
                   if current.get(name) != baseline["files"].get(name))
    if not names:
        raise ValueError("NO_REPAIR_CHANGES: cannot declare successful repair")
    forbidden = [name for name in names if not allowed_path(name) or "link" in current.get(name, {})]
    if forbidden:
        raise ValueError("PROTECTED_OR_UNAPPROVED_CHANGE: " + ", ".join(forbidden))
    for name in names:
        path = root / name
        if path.is_file() and path.stat().st_size > 1024 * 1024:
            raise ValueError("repair source exceeds 1 MiB: " + name)
    return names, current


def run_checks(root, runner=subprocess.run):
    commands = [[sys.executable, "-m", "pytest", "tests/", "-x", "--tb=short"],
                ["node", "--check", "docs/app.js"],
                ["node", "--test", "tests/pages_ui.test.js"]]
    results = {}
    with (root / "_test_after_fix_.txt").open("w", encoding="utf-8") as log:
        for command in commands:
            process = runner(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            log.write("$ " + " ".join(command) + "\n" + (process.stdout or "") + "\n")
            log.flush()
            results[" ".join(command[1:])] = process.returncode
            print("repair verification rc=" + str(process.returncode) + ": " + " ".join(command))
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode, command)
    for name in file_state(root):
        if name.endswith(".py"):
            ast.parse((root / name).read_text(encoding="utf-8-sig"), filename=name)
    import yaml
    yaml.safe_load((root / ".cnb.yml").read_text(encoding="utf-8"))
    results["syntax"] = 0
    return results


def validate(root, state_dir, runner=subprocess.run):
    baseline = json.loads((state_dir / "baseline.json").read_text(encoding="utf-8"))
    names, before_tests = changed_files(root, baseline)
    results = run_checks(root, runner)
    names_after, current = changed_files(root, baseline)
    if current != before_tests or names != names_after:
        raise ValueError("verification altered repair files")
    diff = subprocess.check_output(["git", "diff", "--binary", "HEAD", "--", *names], cwd=root)
    (root / "_repair_diff_.patch").write_bytes(diff)
    # Include source for new untracked files that git diff cannot show.
    with (root / "_repair_diff_.patch").open("ab") as report:
        for name in names:
            if name not in baseline["files"] and (root / name).is_file():
                report.write(("\nNEW FILE: " + name + "\n").encode())
                report.write((root / name).read_bytes())
    fix_report = root / "_fix_report_.md"
    if not fix_report.is_file():
        raise ValueError("repair report missing")
    proposal = {"files": current, "changes": names, "checks": results,
                "fix_report_sha256": hashlib.sha256(fix_report.read_bytes()).hexdigest()}
    (state_dir / "validated.json").write_text(json.dumps(proposal), encoding="utf-8")
    print("actual pytest, Node and syntax checks passed; review required")


def approved_changes(root, state_dir):
    baseline = json.loads((state_dir / "baseline.json").read_text(encoding="utf-8"))
    proposal = json.loads((state_dir / "validated.json").read_text(encoding="utf-8"))
    names, current = changed_files(root, baseline)
    if current != proposal["files"] or names != proposal["changes"]:
        raise ValueError("reviewer changed source, or proposal changed after verification")
    if not proposal["checks"] or any(code != 0 for code in proposal["checks"].values()):
        raise ValueError("actual verification did not pass")
    if hashlib.sha256((root / "_fix_report_.md").read_bytes()).hexdigest() != proposal["fix_report_sha256"]:
        raise ValueError("reviewer changed repair report")
    review = (root / "_review_result_.md").read_text(encoding="utf-8").splitlines()
    if not review or review[0] != "VERDICT: PASS":
        raise ValueError("review verdict must be exactly VERDICT: PASS")
    return names


def next_retry(value):
    if not re.fullmatch(r"[0-9]+", str(value)):
        raise ValueError("invalid RETRY_COUNT")
    current = int(value)
    if current >= 2:
        raise ValueError("RETRY_CAP_REACHED")
    return current + 1


def start_retry(sha, retry, token, branch, debug, opener=urllib.request.urlopen):
    if not re.fullmatch(r"[0-9a-f]{40,64}", sha):
        raise ValueError("retry SHA must pin committed git HEAD")
    body = {"branch": branch, "event": "api_trigger", "sha": sha,
            "env": {"RETRY_COUNT": str(retry), "DEBUG_MODE": debug}}
    request = urllib.request.Request(
        "https://api.cnb.cool/" + REPOSITORY + "/-/build/start",
        data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                 "Accept": "application/vnd.cnb.api+json"})
    with opener(request, timeout=60) as response:
        if not 200 <= response.status < 300:
            raise ValueError("retry HTTP failed: " + str(response.status))
        result = json.loads(response.read())
    if not isinstance(result, dict) or result.get("success") is not True or not result.get("sn"):
        raise ValueError("retry API did not confirm an accepted build")
    print("verified repair retry accepted: " + str(result["sn"]))
    return result


def finalize(root, state_dir):
    if os.environ.get("NPC_BUDGET_STATE") != "RUN":
        raise ValueError("NPC_BUDGET_STATE must be RUN")
    retry = next_retry(os.environ.get("RETRY_COUNT", "0"))
    names = approved_changes(root, state_dir)
    token = os.environ.get("CNB_AUTOFIX_TOKEN") or os.environ.get("CNB_TOKEN")
    if not token:
        raise ValueError("CNB_TOKEN required for safe push and retry")
    branch = os.environ.get("CNB_BRANCH", "main")
    if branch != "main":
        raise ValueError("automated repair publication only supports main")
    git(root, "config", "user.name", "CodeBuddy-deepseek-v4.1-flash")
    git(root, "config", "user.email", "xuerui911@gmail.com")
    git(root, "add", "--", *names)
    git(root, "commit", "--only", "-m", "fix: reviewed CNB NPC repair [skip ci]", "--", *names)
    sha = git(root, "rev-parse", "HEAD")
    committed = sorted(git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", sha).splitlines())
    if committed != sorted(names):
        raise ValueError("commit contains files outside validated repair")
    with tempfile.TemporaryDirectory(prefix="cnb-npc-auth-") as auth_dir:
        askpass = Path(auth_dir) / "askpass.sh"
        askpass.write_text('#!/bin/sh\ncase "$1" in\n*sername*) printf "%s" "${CNB_TOKEN_USER_NAME:-cnb}" ;;\n*) printf "%s" "$CNB_TOKEN" ;;\nesac\n', encoding="utf-8")
        askpass.chmod(0o700)
        env = dict(os.environ, CNB_TOKEN=token, GIT_ASKPASS=str(askpass), GIT_TERMINAL_PROMPT="0")
        subprocess.run(["git", "push", "https://cnb.cool/" + REPOSITORY + ".git", "HEAD:refs/heads/main"],
                       cwd=root, env=env, check=True)
    result = start_retry(sha, retry, token, branch, os.environ.get("DEBUG_MODE", "false"))
    (state_dir / "retry.json").write_text(json.dumps(result), encoding="utf-8")
    print("reviewed repair committed, pushed and pinned retry started")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["snapshot", "validate", "finalize"])
    parser.add_argument("--root", default=".")
    parser.add_argument("--state-dir", default="/tmp/cars-npc-repair")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    state_dir = Path(args.state_dir).resolve()
    try:
        if args.action == "snapshot":
            snapshot(root, state_dir)
        elif args.action == "validate":
            validate(root, state_dir)
        else:
            finalize(root, state_dir)
    except subprocess.CalledProcessError as exc:
        print("repair command failed rc=" + str(exc.returncode), file=sys.stderr)
        return exc.returncode or 1
    except Exception as exc:
        print("repair blocked: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
