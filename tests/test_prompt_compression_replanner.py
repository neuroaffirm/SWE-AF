"""Tests for replanner.py prompt compression.

Validates:
- AC1: replanner.py reduced to ≤182 LOC
- AC2: ReplanDecision output schema requirements preserved
- AC3: DAG restructuring logic guidelines maintained
- AC4: Failure analysis framework intact
- AC5: Dependency graph manipulation rules preserved
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import importlib.util
import sys
from pathlib import Path

import pytest

# Load replanner module directly to avoid circular import from swe_af.prompts package
replanner_path = Path(__file__).parent.parent / "swe_af" / "prompts" / "replanner.py"
spec = importlib.util.spec_from_file_location("replanner", replanner_path)
replanner_module = importlib.util.module_from_spec(spec)
sys.modules["replanner"] = replanner_module
spec.loader.exec_module(replanner_module)

SYSTEM_PROMPT = replanner_module.SYSTEM_PROMPT
replanner_task_prompt = replanner_module.replanner_task_prompt

# Import schemas normally
from swe_af.execution.schemas import DAGState, IssueOutcome, IssueResult


# ---------------------------------------------------------------------------
# AC1: LOC assertion (≤182 lines)
# ---------------------------------------------------------------------------


class TestLOCTarget:
    def test_replanner_py_meets_loc_target(self) -> None:
        """Verify replanner.py is ≤182 LOC (20% reduction from 227)."""
        repo_root = Path(__file__).parent.parent
        replanner_path = repo_root / "swe_af" / "prompts" / "replanner.py"

        result = subprocess.run(
            ["wc", "-l", str(replanner_path)],
            capture_output=True,
            text=True,
            check=True,
        )

        loc = int(result.stdout.split()[0])
        assert loc <= 182, f"replanner.py has {loc} LOC, expected ≤182"


# ---------------------------------------------------------------------------
# AC2: ReplanDecision schema requirements preserved
# ---------------------------------------------------------------------------


class TestReplanDecisionSchema:
    def test_system_prompt_mentions_all_output_fields(self) -> None:
        """Verify SYSTEM_PROMPT documents all ReplanDecision fields."""
        # Required fields in ReplanDecision schema
        required_fields = [
            "updated_issues",
            "new_issues",
            "removed_issue_names",
            "skipped_issue_names",
            "rationale",
        ]

        for field in required_fields:
            assert field in SYSTEM_PROMPT, (
                f"ReplanDecision field '{field}' not documented in SYSTEM_PROMPT"
            )

    def test_system_prompt_specifies_json_output(self) -> None:
        """Verify SYSTEM_PROMPT requires JSON output."""
        assert "JSON" in SYSTEM_PROMPT or "json" in SYSTEM_PROMPT
        assert "ReplanDecision" in SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# AC3: DAG restructuring logic guidelines maintained
# ---------------------------------------------------------------------------


class TestDAGRestructuringLogic:
    def test_system_prompt_documents_all_actions(self) -> None:
        """Verify all ReplanAction values documented in SYSTEM_PROMPT."""
        actions = ["CONTINUE", "MODIFY_DAG", "REDUCE_SCOPE", "ABORT"]

        for action in actions:
            assert action in SYSTEM_PROMPT, (
                f"ReplanAction '{action}' not documented in SYSTEM_PROMPT"
            )

    def test_system_prompt_explains_modify_dag_capabilities(self) -> None:
        """Verify MODIFY_DAG restructuring options preserved."""
        # Key restructuring operations
        operations = ["split", "merge", "simplify", "stub"]

        for op in operations:
            assert op.lower() in SYSTEM_PROMPT.lower(), (
                f"MODIFY_DAG operation '{op}' not mentioned in SYSTEM_PROMPT"
            )


# ---------------------------------------------------------------------------
# AC4: Failure analysis framework intact (5-step decision)
# ---------------------------------------------------------------------------


class TestFailureAnalysisFramework:
    def test_system_prompt_has_decision_framework(self) -> None:
        """Verify 5-step decision framework preserved."""
        # Framework should be present
        assert "Decision Framework" in SYSTEM_PROMPT or "Framework" in SYSTEM_PROMPT

        # Key questions from 5-step framework
        keywords = ["essential", "simplify", "alternative", "stub", "unrecoverable"]

        for keyword in keywords:
            assert keyword.lower() in SYSTEM_PROMPT.lower(), (
                f"Decision framework keyword '{keyword}' missing from SYSTEM_PROMPT"
            )


# ---------------------------------------------------------------------------
# AC5: Dependency graph manipulation rules preserved
# ---------------------------------------------------------------------------


class TestDependencyGraphRules:
    def test_system_prompt_documents_constraints(self) -> None:
        """Verify constraints on what replanner cannot do."""
        constraints = [
            "completed",  # Cannot modify completed work
            "retry",      # Cannot retry exact same approach
        ]

        for constraint in constraints:
            assert constraint.lower() in SYSTEM_PROMPT.lower(), (
                f"Constraint '{constraint}' not documented in SYSTEM_PROMPT"
            )


# ---------------------------------------------------------------------------
# Functional test: Run replanner_task_prompt with reference scenario
# ---------------------------------------------------------------------------


class TestFunctionalCorrectness:
    def test_task_prompt_builds_with_reference_failure_scenario(self) -> None:
        """Verify replanner_task_prompt builds valid prompt for failure scenario."""
        # Create minimal DAGState with 3 issues, 1 failed
        dag_state = DAGState(
            repo_path="/test/repo",
            artifacts_dir="/test/artifacts",
            prd_path="/test/artifacts/prd.md",
            architecture_path="/test/artifacts/architecture.md",
            issues_dir="/test/artifacts/issues",
            original_plan_summary="Test plan",
            prd_summary="Test PRD",
            architecture_summary="Test architecture",
            all_issues=[
                {"name": "issue-1", "title": "First issue", "depends_on": [], "provides": ["feature-a"]},
                {"name": "issue-2", "title": "Second issue", "depends_on": ["issue-1"], "provides": ["feature-b"]},
                {"name": "issue-3", "title": "Third issue", "depends_on": ["issue-2"], "provides": ["feature-c"]},
            ],
            levels=[["issue-1"], ["issue-2"], ["issue-3"]],
            completed_issues=[],
            failed_issues=[],
            skipped_issues=[],
            replan_count=0,
            max_replans=2,
            replan_history=[],
        )

        # Create failed issue result
        failed_issues = [
            IssueResult(
                issue_name="issue-2",
                outcome=IssueOutcome.FAILED_UNRECOVERABLE,
                result_summary="Failed to implement feature-b",
                error_message="Compilation error in module B",
                error_context="Error: undefined reference to function_x\nFile: b.py:42",
                attempts=3,
                files_changed=["b.py"],
            )
        ]

        # Build prompt
        prompt = replanner_task_prompt(
            dag_state=dag_state,
            failed_issues=failed_issues,
            escalation_notes=None,
            adaptation_history=None,
        )

        # Verify prompt contains key sections
        assert "## Original Plan" in prompt
        assert "## PRD" in prompt
        assert "## Architecture" in prompt
        assert "## References" in prompt or "## Reference" in prompt
        assert "## Full DAG" in prompt or "## DAG" in prompt
        assert "## Failed" in prompt
        assert "issue-2" in prompt
        assert "Compilation error" in prompt
        assert "## Task" in prompt

    def test_task_prompt_handles_empty_escalation_notes(self) -> None:
        """Verify graceful handling of empty escalation_notes."""
        dag_state = DAGState(
            repo_path="/test",
            all_issues=[{"name": "test", "depends_on": [], "provides": []}],
            levels=[["test"]],
            completed_issues=[],
            failed_issues=[],
            skipped_issues=[],
        )

        failed_issues = [
            IssueResult(
                issue_name="test",
                outcome=IssueOutcome.FAILED_UNRECOVERABLE,
                result_summary="Test failure",
                error_message="Test error",
                attempts=1,
            )
        ]

        # Should not raise with None
        prompt1 = replanner_task_prompt(dag_state, failed_issues, escalation_notes=None)
        assert isinstance(prompt1, str)
        assert len(prompt1) > 0

        # Should not raise with empty list
        prompt2 = replanner_task_prompt(dag_state, failed_issues, escalation_notes=[])
        assert isinstance(prompt2, str)
        assert len(prompt2) > 0

    def test_task_prompt_handles_missing_adaptation_history(self) -> None:
        """Verify graceful handling of missing adaptation_history."""
        dag_state = DAGState(
            repo_path="/test",
            all_issues=[{"name": "test", "depends_on": [], "provides": []}],
            levels=[["test"]],
            completed_issues=[],
            failed_issues=[],
            skipped_issues=[],
        )

        failed_issues = [
            IssueResult(
                issue_name="test",
                outcome=IssueOutcome.FAILED_UNRECOVERABLE,
                result_summary="Test failure",
                error_message="Test error",
                attempts=1,
            )
        ]

        # Should not raise with None
        prompt = replanner_task_prompt(dag_state, failed_issues, adaptation_history=None)
        assert isinstance(prompt, str)
        assert len(prompt) > 0


# ---------------------------------------------------------------------------
# DAG validity checks
# ---------------------------------------------------------------------------


class TestDAGValidity:
    def test_task_prompt_shows_dependency_structure(self) -> None:
        """Verify task prompt shows dependency relationships."""
        dag_state = DAGState(
            repo_path="/test",
            all_issues=[
                {"name": "a", "depends_on": [], "provides": ["x"]},
                {"name": "b", "depends_on": ["a"], "provides": ["y"]},
            ],
            levels=[["a"], ["b"]],
            completed_issues=[],
            failed_issues=[],
            skipped_issues=[],
        )

        failed_issues = [
            IssueResult(
                issue_name="a",
                outcome=IssueOutcome.FAILED_UNRECOVERABLE,
                result_summary="Failed",
                error_message="Error",
                attempts=1,
            )
        ]

        prompt = replanner_task_prompt(dag_state, failed_issues)

        # Should show dependencies
        assert "depends" in prompt.lower() or "deps" in prompt.lower()
        assert "provides" in prompt.lower()

        # Should show issue names
        assert "a" in prompt
        assert "b" in prompt
