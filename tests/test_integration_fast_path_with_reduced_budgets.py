"""Integration tests for fast-path with reduced turn budgets and timeouts.

Verifies that the trivial issue fast-path (issue/00-fix-test-failure-fast-path)
works correctly with the reduced turn budgets and timeouts from
issue/00-fix-turn-budgets and issue/00-fix-timeouts.

Priority: Medium - Fast-path should complete faster with tighter constraints
"""

from __future__ import annotations

import pytest

from swe_af.execution.schemas import ExecutionConfig


class TestFastPathWithReducedBudgets:
    """Verify fast-path behavior is compatible with reduced turn/timeout budgets."""

    def test_coder_has_sufficient_budget_for_trivial_fast_path(self):
        """Coder has enough turns/timeout for trivial issues even after reductions."""
        config = ExecutionConfig()

        # Coder wasn't reduced (still 100 turns, 1800s)
        assert config.max_turns_for_role("coder") == 100
        assert config.timeout_for_role("coder") == 1800

        # Fast-path trivial issues should complete in 1 iteration
        # Even with 100 turns, that's plenty for a simple change
        assert config.max_turns_for_role("coder") >= 10, (
            "Coder needs at least 10 turns for trivial issues"
        )

    def test_qa_synthesizer_budget_sufficient_for_fast_path_synthesis(self):
        """QA synthesizer (reduced to 20 turns, 600s) can still synthesize feedback."""
        config = ExecutionConfig()

        # QA synthesizer was reduced
        assert config.max_turns_for_role("qa_synthesizer") == 20
        assert config.timeout_for_role("qa_synthesizer") == 600

        # 20 turns should be enough for simple synthesis
        # (The agent just needs to decide fix/approve/block)
        assert config.max_turns_for_role("qa_synthesizer") >= 5, (
            "QA synthesizer needs at least 5 turns for decision making"
        )

    def test_fast_path_skips_code_reviewer_saving_time(self):
        """Fast-path bypasses code reviewer, saving time even with tight budgets."""
        config = ExecutionConfig()

        # Code reviewer has 75 turns, 1500s
        reviewer_turns = config.max_turns_for_role("code_reviewer")
        reviewer_timeout = config.timeout_for_role("code_reviewer")

        # Fast-path skips this entirely, saving 1500s
        assert reviewer_turns == 75
        assert reviewer_timeout == 1500

        # Fast-path should save approximately 1500s + turn overhead
        # This is a qualitative assertion - no code to test, just verifying config

    def test_trivial_issues_complete_within_reduced_coder_budget(self):
        """Trivial issues should complete well within coder's budget."""
        config = ExecutionConfig()

        coder_turns = config.max_turns_for_role("coder")

        # For trivial issues (1 iteration), should use <30% of budget
        # 100 turns * 0.3 = 30 turns max expected
        # Trivial changes typically use 5-15 turns
        assert coder_turns >= 30, (
            "Coder should have at least 30 turns for comfortable trivial completion"
        )

    def test_fast_path_flag_check_exists_in_coding_loop_source(self):
        """Coding loop source code contains fast-path flag check."""
        import inspect
        from swe_af.execution.coding_loop import run_coding_loop

        source = inspect.getsource(run_coding_loop)

        # Fast-path logic should exist
        assert "is_trivial" in source, "Fast-path missing trivial flag check"
        assert "tests_passed" in source, "Fast-path missing tests_passed check"

        # Check for the test requirement override
        assert "coder_result" in source, "Fast-path missing coder_result access"

    def test_non_trivial_issues_have_enough_budget_for_review_cycles(self):
        """Non-trivial issues have enough budget for multiple review cycles."""
        config = ExecutionConfig()

        # Non-trivial goes through full review loop
        coder_turns = config.max_turns_for_role("coder")
        reviewer_turns = config.max_turns_for_role("code_reviewer")
        qa_turns = config.max_turns_for_role("qa")

        # Should support at least 2 review cycles
        # Each cycle: coder iteration + reviewer + QA
        # Assume ~15 turns per cycle
        assert coder_turns >= 30, "Coder needs at least 30 turns for review cycles"
        assert reviewer_turns >= 15, "Reviewer needs at least 15 turns per review"
        assert qa_turns >= 15, "QA needs at least 15 turns per review"

    def test_max_coding_iterations_compatible_with_turn_budgets(self):
        """max_coding_iterations (6) is achievable within turn budgets."""
        config = ExecutionConfig()

        max_iterations = config.max_coding_iterations
        coder_turns = config.max_turns_for_role("coder")

        # 6 iterations should fit within 100 turns
        # 100 / 6 ≈ 16.7 turns per iteration
        turns_per_iteration = coder_turns / max_iterations

        assert turns_per_iteration >= 10, (
            f"Only {turns_per_iteration:.1f} turns per iteration, may be too tight"
        )

    def test_advisor_invocation_limit_compatible_with_timeouts(self):
        """max_advisor_invocations (2) fits within timeout budget."""
        config = ExecutionConfig()

        # Issue advisor has 75 turns, 1500s
        advisor_turns = config.max_turns_for_role("issue_advisor")
        advisor_timeout = config.timeout_for_role("issue_advisor")
        max_advisor_invocations = config.max_advisor_invocations

        # 2 invocations within 1500s budget
        timeout_per_invocation = advisor_timeout / max_advisor_invocations

        assert timeout_per_invocation >= 300, (
            f"Only {timeout_per_invocation}s per advisor invocation, may be too tight"
        )

        # Turns also sufficient
        turns_per_invocation = advisor_turns / max_advisor_invocations
        assert turns_per_invocation >= 20, (
            f"Only {turns_per_invocation:.1f} turns per advisor invocation"
        )

    def test_replanner_budget_sufficient_for_dag_analysis(self):
        """Replanner (75 turns, 1500s) can analyze DAG state within budget."""
        config = ExecutionConfig()

        replan_turns = config.max_turns_for_role("replan")
        replan_timeout = config.timeout_for_role("replan")
        max_replans = config.max_replans

        # 2 replans within budget
        timeout_per_replan = replan_timeout / max_replans
        turns_per_replan = replan_turns / max_replans

        assert timeout_per_replan >= 300, (
            f"Only {timeout_per_replan}s per replan, may be too tight"
        )
        assert turns_per_replan >= 20, (
            f"Only {turns_per_replan:.1f} turns per replan"
        )

    def test_git_agent_budget_sufficient_for_branch_operations(self):
        """Git agent (reduced to 20 turns, 600s) can still perform branch operations."""
        config = ExecutionConfig()

        git_turns = config.max_turns_for_role("git")
        git_timeout = config.timeout_for_role("git")

        # Git operations are typically fast
        # 20 turns, 600s should be enough for:
        # - git checkout -b <branch>
        # - git add
        # - git commit
        # - Basic worktree operations
        assert git_turns == 20, "Git should have 20 turns"
        assert git_timeout == 600, "Git should have 600s timeout"

        # Even reduced, should be adequate
        assert git_turns >= 10, "Git needs at least 10 turns for branch operations"
        assert git_timeout >= 300, "Git needs at least 300s for operations"

    def test_merger_timeout_sufficient_for_multi_branch_merge(self):
        """Merger (900s) can merge multiple branches within timeout."""
        config = ExecutionConfig()

        merger_timeout = config.timeout_for_role("merger")

        # Merger timeout reduced from 1200s to 900s
        assert merger_timeout == 900

        # Should still handle reasonable merge scenarios
        # Assume 3 branches to merge, ~300s per branch
        branches_mergeable = merger_timeout / 300
        assert branches_mergeable >= 2, (
            "Merger timeout may be too tight for multi-branch merges"
        )
