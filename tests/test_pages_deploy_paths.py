from pathlib import Path

from scripts.validate_workflow_expectations import PAGES_PUSH_DEPENDENCIES, pages_push_paths_cover


def test_pages_push_paths_cover_the_traced_build_and_schema_dependencies():
    workflow = Path(__file__).resolve().parents[1] / ".github/workflows/merge-and-filter.yml"
    missing = pages_push_paths_cover(workflow, PAGES_PUSH_DEPENDENCIES)
    assert missing == []
