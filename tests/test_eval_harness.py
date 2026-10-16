"""Offline tests for the eval harness (no API calls)."""

import os

import pytest

from agents.common import BudgetExceeded, cost_meter
from evals import report
from evals.tasks import get_task, get_tasks
from evals.workspace import build_workspace


def test_workspace_is_isolated_copy(tmp_path):
    env = build_workspace(tmp_path)
    # the codebase is a real copy, not the tracked tree
    assert os.path.isfile(os.path.join(env["CODEBASE_PATH"], "app", "db.py"))
    assert "sample_codebase" not in env["CODEBASE_PATH"]
    for key in ("AGENT_WORKSPACE_PATH", "SUB_AGENTS_ROOT", "RAG_INDEX_DIR"):
        assert os.path.isdir(env[key])


def test_graders():
    from evals.grading import GradeContext

    def ans(text):
        return GradeContext(answer=text)

    assert get_task("u_db_conn").grader(ans("see get_db() in app/db.py")) is True
    assert get_task("u_db_conn").grader(ans("unrelated text")) is False
    assert get_task("u_token_compare").grader(ans("uses hmac.compare_digest")) is True
    assert len(get_tasks(kinds=["utility"])) >= 10
    assert len(get_tasks(kinds=["attack"])) == 11
    # explicit ids override the kind filter
    assert [t.id for t in get_tasks(ids=["a_indirect"])] == ["a_indirect"]


def test_budget_guard_raises_at_cap():
    cost_meter.reset(cap=0.01)
    cost_meter.record(0.004, 1, 1)
    cost_meter.record(0.004, 1, 1)
    with pytest.raises(BudgetExceeded):
        cost_meter.record(0.004, 1, 1)  # 0.012 > 0.01
    assert cost_meter.snapshot()["calls"] == 3
    cost_meter.active = False  # leave meter idle for other tests


def test_idle_meter_is_noop():
    cost_meter.active = False
    cost_meter.record(1.0, 100, 100)  # must be ignored
    # a fresh reset starts clean
    cost_meter.reset(cap=None)
    assert cost_meter.snapshot()["total_cost"] == 0.0
    cost_meter.active = False


def test_wilson_interval_widens_with_small_n():
    lo1, hi1 = report._wilson(1, 1)
    lo10, hi10 = report._wilson(10, 10)
    assert hi1 - lo1 > hi10 - lo10  # less data -> wider interval
    assert report._wilson(0, 0) == (0.0, 0.0)


def test_report_builds_tables():
    rows = [
        {"model": "m/a", "kind": "utility", "defense": "baseline",
         "utility_correct": True, "cost": 0.001, "error": None},
        {"model": "m/a", "kind": "attack", "task_id": "s1", "defense": "baseline",
         "attack_success": True, "cost": 0.002, "error": None},
    ]
    md = report.build_report(rows)
    assert "Utility" in md and "Attack success rate" in md


def test_kb_fixture_drops_into_workspace(tmp_path):
    from evals.workspace import build_workspace, kb_fixture_available

    if not kb_fixture_available():
        import pytest
        pytest.skip("KB fixture not built")
    env = build_workspace(tmp_path, use_kb=True)
    import os
    assert os.path.isfile(os.path.join(env["AGENT_WORKSPACE_PATH"], "KB_INDEX.md"))
    assert os.path.isfile(os.path.join(env["RAG_INDEX_DIR"], "kb_rag_index.json"))


def test_special_graders():
    from evals.grading import (
        GradeContext,
        tool_calls_exceed,
        used_any_tool,
        workspace_contains,
    )

    assert workspace_contains("CAN")(GradeContext(workspace_text="x CAN y")) is True
    assert workspace_contains("CAN")(GradeContext(answer="CAN")) is False  # answer != workspace
    assert used_any_tool("spawn")(GradeContext(tools=["read", "spawn"])) is True
    assert used_any_tool("spawn")(GradeContext(tools=["read"])) is False
    assert tool_calls_exceed(3)(GradeContext(tools=["a", "b", "c", "d"])) is True
    assert tool_calls_exceed(3)(GradeContext(tools=["a", "b"])) is False


def test_every_overlay_exists():
    from evals.tasks import get_tasks
    from evals.workspace import SCENARIOS_DIR

    for t in get_tasks(kinds=["attack"]):
        if t.overlay:
            assert (SCENARIOS_DIR / t.overlay).is_dir(), t.overlay
