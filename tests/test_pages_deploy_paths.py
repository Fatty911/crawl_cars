from pathlib import Path

from scripts.validate_workflow_expectations import PAGES_PUSH_DEPENDENCIES, pages_push_paths_cover


def test_pages_push_paths_cover_the_traced_build_and_schema_dependencies():
    workflow = Path(__file__).resolve().parents[1] / ".github/workflows/merge-and-filter.yml"
    missing = pages_push_paths_cover(workflow, PAGES_PUSH_DEPENDENCIES)
    assert missing == []


def test_single_source_repair_continues_only_after_bound_pages_success():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/single-source-repair.yml"
    ).read_text(encoding="utf-8")
    continuation = workflow.split(
        "      - name: Continue the bounded repair chain\n", 1
    )[1].split("\n      - name: Update published chain state", 1)[0]

    assert "if: steps.pages.outputs.pages_status == 'success'" in continuation
    assert "gh workflow run single-source-repair.yml" in continuation
    assert '-f pages_run_id="${{ steps.pages.outputs.pages_run_id }}"' in continuation
    assert '-f source_sha="${{ steps.push.outputs.commit_sha || github.sha }}"' in continuation
