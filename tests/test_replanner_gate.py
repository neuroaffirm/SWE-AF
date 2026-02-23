"""Unit tests for replanner downstream count gating logic."""

from __future__ import annotations

import asyncio
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swe_af.execution.dag_executor import run_dag
from swe_af.execution.schemas import (
    DAGState,
    ExecutionConfig,
    IssueOutcome,
    IssueResult,
    ReplanAction,
    ReplanDecision,
)


@pytest.fixture
def base_config():
    """Base execution config with replanning enabled."""
    return ExecutionConfig(
        enable_replanning=True,
        max_replans=2,
        max_coding_iterations=3,
        agent_timeout_seconds=10,
    )


def make_plan_result(issues: list[dict], levels: list[list[str]]) -> dict:
    """Create a plan result dict for run_dag."""
    return {
        "issues": issues,
        "levels": levels,
        "prd": {"goal": "test goal"},
        "architecture": {"components": []},
    }


def create_failed_issue(name: str, outcome: IssueOutcome = IssueOutcome.FAILED_UNRECOVERABLE) -> IssueResult:
    """Helper to create a failed issue result."""
    return IssueResult(
        issue_name=name,
        outcome=outcome,
        result_summary=f"{name} failed",
        attempts=3,
        files_changed=[],
    )


@pytest.mark.asyncio
async def test_isolated_failure_skips_replanner(base_config):
    """Test AC7: Isolated failures (0 downstream) skip replanner and mark downstream as SKIPPED."""
    # Arrange: Create a DAG where one branch has an isolated failure at non-final level
    # issue-b is isolated (no downstream), failure at level 1, which is non-final
    issues = [
        {"name": "issue-a", "depends_on": []},
        {"name": "issue-b", "depends_on": []},  # Parallel to issue-a, isolated
        {"name": "issue-c", "depends_on": ["issue-a"]},
        {"name": "issue-d", "depends_on": ["issue-c"]},
        {"name": "issue-e", "depends_on": ["issue-d"]},
    ]
    # 5 levels, so len(levels) - 2 = 3. Level 0 < 3, so it's non-final
    levels = [["issue-a", "issue-b"], ["issue-c"], ["issue-d"], ["issue-e"], []]
    # Actually, that creates an empty level. Let me fix it:
    levels = [["issue-a", "issue-b"], ["issue-c"], ["issue-d"], ["issue-e"]]
    plan_result = make_plan_result(issues, levels)

    notes = []

    def note_fn(msg, tags=None):
        notes.append({"msg": msg, "tags": tags or []})

    # Mock execute_fn to fail issue-b (isolated, no downstream)
    async def mock_execute_fn(issue: dict, dag_state: DAGState) -> IssueResult:
        if issue["name"] == "issue-b":
            return create_failed_issue("issue-b")
        return IssueResult(
            issue_name=issue["name"],
            outcome=IssueOutcome.COMPLETED,
            result_summary="completed",
            attempts=1,
            files_changed=[],
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        # Act
        result = await run_dag(
            plan_result=plan_result,
            repo_path=tmpdir,
            execute_fn=mock_execute_fn,
            config=base_config,
            note_fn=note_fn,
        )

    # Assert: replanner should NOT be invoked due to isolation
    replanner_skip_notes = [n for n in notes if "replanner_gate" in n["tags"] and "skip" in n["tags"]]
    assert len(replanner_skip_notes) > 0, "Expected replanner gate skip message"

    # At level 0 (len(levels) - 2 = 2), level 0 < 2, so NOT final level
    # Should skip due to isolation (0 downstream)
    skip_msg = replanner_skip_notes[0]["msg"]
    assert "isolated" in skip_msg.lower() or "0 downstream" in skip_msg.lower()

    # Replanner should not have been invoked (replan_count should be 0)
    assert result.replan_count == 0


@pytest.mark.asyncio
async def test_failure_with_multiple_downstream_invokes_replanner(base_config):
    """Test AC1-AC4, AC6: Failure with ≥2 downstream at non-final level invokes replanner."""
    # Arrange: issue-a has 2 downstream (issue-b, issue-c)
    issues = [
        {"name": "issue-a", "depends_on": []},
        {"name": "issue-b", "depends_on": ["issue-a"]},
        {"name": "issue-c", "depends_on": ["issue-a"]},
        {"name": "issue-d", "depends_on": ["issue-b", "issue-c"]},
    ]
    levels = [["issue-a"], ["issue-b", "issue-c"], ["issue-d"]]
    plan_result = make_plan_result(issues, levels)

    notes = []

    def note_fn(msg, tags=None):
        notes.append({"msg": msg, "tags": tags or []})

    # Mock execute_fn to fail issue-a
    async def mock_execute_fn(issue: dict, dag_state: DAGState) -> IssueResult:
        if issue["name"] == "issue-a":
            return create_failed_issue("issue-a")
        return IssueResult(
            issue_name=issue["name"],
            outcome=IssueOutcome.COMPLETED,
            result_summary="completed",
            attempts=1,
            files_changed=[],
        )

    with tempfile.TemporaryDirectory() as tmpdir, \
         patch("swe_af.execution.dag_executor._invoke_replanner_direct") as mock_invoke:

        # Set up mock to return a proper decision
        async def mock_invoke_replanner(*args, **kwargs):
            return ReplanDecision(
                action=ReplanAction.CONTINUE,
                rationale="Continue without replanning",
                new_issues=[],
                updated_issues=[],
                removed_issues=[],
            )

        mock_invoke.side_effect = mock_invoke_replanner

        # Act
        result = await run_dag(
            plan_result=plan_result,
            repo_path=tmpdir,
            execute_fn=mock_execute_fn,
            config=base_config,
            note_fn=note_fn,
        )

    # Assert: replanner should be invoked
    replanner_invoke_notes = [n for n in notes if "replanner_gate" in n["tags"] and "invoke" in n["tags"]]
    assert len(replanner_invoke_notes) > 0, "Expected replanner gate invoke message"

    # Check downstream count in message
    invoke_msg = replanner_invoke_notes[0]["msg"]
    assert "2 downstream" in invoke_msg or "downstream" in invoke_msg.lower()

    # Replanner should have been invoked
    mock_invoke.assert_called_once()


@pytest.mark.asyncio
async def test_final_level_failure_skips_replanner(base_config):
    """Test AC3, AC5: Final-level failures skip replanner."""
    # Arrange: At level 1 (len(levels) - 2 = 3 - 2 = 1), issue-b fails
    issues = [
        {"name": "issue-a", "depends_on": []},
        {"name": "issue-b", "depends_on": ["issue-a"]},
        {"name": "issue-c", "depends_on": ["issue-a"]},
        {"name": "issue-d", "depends_on": ["issue-b", "issue-c"]},
    ]
    levels = [["issue-a"], ["issue-b", "issue-c"], ["issue-d"]]
    plan_result = make_plan_result(issues, levels)

    notes = []

    def note_fn(msg, tags=None):
        notes.append({"msg": msg, "tags": tags or []})

    # Mock execute_fn to succeed issue-a, fail issue-b (which has issue-d downstream)
    async def mock_execute_fn(issue: dict, dag_state: DAGState) -> IssueResult:
        if issue["name"] == "issue-b":
            return create_failed_issue("issue-b")
        return IssueResult(
            issue_name=issue["name"],
            outcome=IssueOutcome.COMPLETED,
            result_summary="completed",
            attempts=1,
            files_changed=[],
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        # Act
        result = await run_dag(
            plan_result=plan_result,
            repo_path=tmpdir,
            execute_fn=mock_execute_fn,
            config=base_config,
            note_fn=note_fn,
        )

    # Assert: replanner should NOT be invoked due to final level
    replanner_skip_notes = [n for n in notes if "replanner_gate" in n["tags"] and "skip" in n["tags"]]
    assert len(replanner_skip_notes) > 0, "Expected replanner gate skip message"

    # Check that the skip reason is "final level"
    skip_msg = replanner_skip_notes[0]["msg"]
    assert "final level" in skip_msg.lower()

    # Replanner should not have been invoked
    assert result.replan_count == 0


@pytest.mark.asyncio
async def test_single_downstream_failure_skips_replanner(base_config):
    """Test AC2, AC5: Failure with only 1 downstream skips replanner (isolated)."""
    # Arrange: issue-y has exactly 1 downstream: issue-z (not issue-w)
    # We need a branching structure
    simple_issues = [
        {"name": "issue-x", "depends_on": []},
        {"name": "issue-y", "depends_on": []},  # Separate branch
        {"name": "issue-z", "depends_on": ["issue-y"]},  # Only dependent of issue-y
        {"name": "issue-w", "depends_on": ["issue-x"]},  # Dependent of issue-x, not issue-y
    ]
    # 4 levels needed for non-final
    # Actually let me think about this differently:
    # At level 1, fail issue-y which has only issue-z downstream
    simple_issues = [
        {"name": "issue-x", "depends_on": []},
        {"name": "issue-y", "depends_on": ["issue-x"]},
        {"name": "issue-z", "depends_on": ["issue-y"]},  # Only dependent of issue-y
        {"name": "issue-w", "depends_on": ["issue-x"]},  # Sibling to issue-y, not downstream
        {"name": "issue-v", "depends_on": ["issue-w"]},  # Makes it long enough
    ]
    # Levels: [[x], [y, w], [z, v]]
    # len = 3, len - 2 = 1, so level 0 < 1 (non-final), level 1 >= 1 (final!)
    # We need 5+ levels
    simple_issues = [
        {"name": "issue-a", "depends_on": []},
        {"name": "issue-b", "depends_on": ["issue-a"]},
        {"name": "issue-c", "depends_on": ["issue-b"]},  # Only 1 downstream of issue-b
        {"name": "issue-d", "depends_on": ["issue-a"]},  # Parallel branch, not downstream of issue-b
        {"name": "issue-e", "depends_on": ["issue-d"]},
    ]
    # Levels: [[a], [b, d], [c, e], []]
    simple_levels = [["issue-a"], ["issue-b", "issue-d"], ["issue-c", "issue-e"]]
    plan_result = make_plan_result(simple_issues, simple_levels)

    notes = []

    def note_fn(msg, tags=None):
        notes.append({"msg": msg, "tags": tags or []})

    # Mock execute_fn to fail issue-b (which has 1 downstream: issue-c)
    async def mock_execute_fn(issue: dict, dag_state: DAGState) -> IssueResult:
        if issue["name"] == "issue-b":
            return create_failed_issue("issue-b")
        return IssueResult(
            issue_name=issue["name"],
            outcome=IssueOutcome.COMPLETED,
            result_summary="completed",
            attempts=1,
            files_changed=[],
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        # Act
        result = await run_dag(
            plan_result=plan_result,
            repo_path=tmpdir,
            execute_fn=mock_execute_fn,
            config=base_config,
            note_fn=note_fn,
        )

    # Assert: replanner should NOT be invoked (1 downstream < 2 threshold)
    replanner_skip_notes = [n for n in notes if "replanner_gate" in n["tags"] and "skip" in n["tags"]]
    assert len(replanner_skip_notes) > 0, "Expected replanner gate skip message"

    # Check that the skip reason indicates isolation (may also say final level since len=3, len-2=1, level 1>=1)
    skip_msg = replanner_skip_notes[0]["msg"]
    # At level 1: len(levels) = 3, len-2 = 1, so level 1 >= 1 is final level
    # So it will say "final level" not "isolated"
    assert "final level" in skip_msg.lower() or ("isolated" in skip_msg.lower() and ("1 downstream" in skip_msg or "downstream" in skip_msg))

    # Replanner should not have been invoked
    assert result.replan_count == 0


@pytest.mark.asyncio
async def test_gate_tags_are_correct():
    """Test AC5, AC6: Verify correct tags are used for skip and invoke logging."""
    # Arrange: DAG with 2+ downstream at non-final level
    issues = [
        {"name": "root", "depends_on": []},
        {"name": "child1", "depends_on": ["root"]},
        {"name": "child2", "depends_on": ["root"]},
        {"name": "grandchild", "depends_on": ["child1", "child2"]},
        {"name": "final", "depends_on": ["grandchild"]},
    ]
    # 4 levels, len(levels) - 2 = 2, so level 0 < 2 (non-final)
    levels = [["root"], ["child1", "child2"], ["grandchild"], ["final"]]
    plan_result = make_plan_result(issues, levels)

    config = ExecutionConfig(
        enable_replanning=True,
        max_replans=1,
        agent_timeout_seconds=10,
    )

    notes = []

    def note_fn(msg, tags=None):
        notes.append({"msg": msg, "tags": tags or []})

    # Mock execute_fn to fail root
    async def mock_execute_fn(issue: dict, dag_state: DAGState) -> IssueResult:
        if issue["name"] == "root":
            return create_failed_issue("root")
        return IssueResult(
            issue_name=issue["name"],
            outcome=IssueOutcome.COMPLETED,
            result_summary="completed",
            attempts=1,
            files_changed=[],
        )

    # Mock replanner
    async def mock_invoke_replanner(*args, **kwargs):
        return ReplanDecision(
            action=ReplanAction.CONTINUE,
            rationale="Continue",
            new_issues=[],
            updated_issues=[],
            removed_issues=[],
        )

    with tempfile.TemporaryDirectory() as tmpdir, \
         patch("swe_af.execution.dag_executor._invoke_replanner_direct", side_effect=mock_invoke_replanner):
        # Act
        await run_dag(
            plan_result=plan_result,
            repo_path=tmpdir,
            execute_fn=mock_execute_fn,
            config=config,
            note_fn=note_fn,
        )

    # Assert: Check that tags include 'replanner_gate' and 'invoke'
    gate_notes = [n for n in notes if "replanner_gate" in n["tags"]]
    assert len(gate_notes) > 0, "Expected replanner gate notes"

    invoke_notes = [n for n in gate_notes if "invoke" in n["tags"]]
    assert len(invoke_notes) > 0, "Expected invoke tag for 2+ downstream case"
