"""Integration tests for turn budget and timeout interaction.

This test verifies that the turn budget and timeout reductions from
issue/00-fix-turn-budgets and issue/00-fix-timeouts work together correctly
without conflicts in ExecutionConfig.

Priority: High - Both features modify the same ExecutionConfig class
"""

from __future__ import annotations

import pytest

from swe_af.execution.schemas import ExecutionConfig, BuildConfig


class TestTurnBudgetTimeoutInteraction:
    """Verify turn budgets and timeouts work together correctly."""

    def test_all_reduced_roles_have_both_turn_and_timeout_set(self):
        """All roles reduced in turn budgets also have timeout values set."""
        config = ExecutionConfig()

        # Roles that were reduced in turn budgets
        reduced_turn_roles = [
            ("git", 20, 600),
            ("issue_writer", 25, 600),
            ("qa_synthesizer", 20, 600),
            ("sprint_planner", 40, 1200),
        ]

        for role, expected_turns, expected_timeout in reduced_turn_roles:
            actual_turns = config.max_turns_for_role(role)
            actual_timeout = config.timeout_for_role(role)

            assert actual_turns == expected_turns, (
                f"{role} turn budget mismatch: expected {expected_turns}, got {actual_turns}"
            )
            assert actual_timeout == expected_timeout, (
                f"{role} timeout mismatch: expected {expected_timeout}, got {actual_timeout}"
            )

    def test_timeout_values_align_with_turn_budgets(self):
        """Timeout values are proportional to turn budgets for lightweight roles."""
        config = ExecutionConfig()

        # Lightweight roles should have lower timeouts matching lower turn budgets
        lightweight_roles = {
            "git": (20, 600),  # 10 min
            "issue_writer": (25, 600),  # 10 min
            "qa_synthesizer": (20, 600),  # 10 min
        }

        for role, (turns, timeout) in lightweight_roles.items():
            assert config.max_turns_for_role(role) == turns
            assert config.timeout_for_role(role) == timeout

            # Verify ratio: 600s / 20-25 turns ≈ 24-30s per turn
            ratio = timeout / turns
            assert 20 <= ratio <= 35, (
                f"{role} timeout/turn ratio {ratio:.1f}s is outside expected range (20-35s)"
            )

    def test_heavier_roles_have_proportionally_higher_timeouts(self):
        """Heavier roles (more turns) have proportionally higher timeouts."""
        config = ExecutionConfig()

        # Coder: 100 turns, 1800s (30 min) = 18s per turn
        coder_ratio = config.timeout_for_role("coder") / config.max_turns_for_role("coder")
        assert 15 <= coder_ratio <= 25, f"Coder ratio {coder_ratio:.1f}s per turn is out of range"

        # QA: 75 turns, 1500s (25 min) = 20s per turn
        qa_ratio = config.timeout_for_role("qa") / config.max_turns_for_role("qa")
        assert 15 <= qa_ratio <= 25, f"QA ratio {qa_ratio:.1f}s per turn is out of range"

    def test_no_role_has_zero_turns_or_timeout(self):
        """All defined roles have positive turns and timeouts."""
        config = ExecutionConfig()

        all_roles = [
            "pm", "architect", "tech_lead", "sprint_planner",
            "issue_writer", "coder", "qa", "code_reviewer",
            "qa_synthesizer", "issue_advisor", "replan",
            "verifier", "retry_advisor", "git", "merger",
            "integration_tester",
        ]

        for role in all_roles:
            turns = config.max_turns_for_role(role)
            timeout = config.timeout_for_role(role)

            assert turns > 0, f"{role} has invalid turns: {turns}"
            assert timeout > 0, f"{role} has invalid timeout: {timeout}"

    def test_build_config_passes_values_to_execution_config(self):
        """BuildConfig correctly passes turn and timeout overrides to ExecutionConfig."""
        build_config = BuildConfig(
            agent_max_turns=200,
            agent_timeout_seconds=3600,
        )

        exec_dict = build_config.to_execution_config_dict()

        assert exec_dict["agent_max_turns"] == 200
        assert exec_dict["agent_timeout_seconds"] == 3600

    def test_execution_config_overrides_preserve_per_role_values(self):
        """Custom ExecutionConfig overrides don't break per-role values."""
        config = ExecutionConfig(
            agent_max_turns=200,  # Global default
            git_turns=15,  # Override git specifically
            git_timeout=300,  # Override git timeout
        )

        # Custom overrides work
        assert config.max_turns_for_role("git") == 15
        assert config.timeout_for_role("git") == 300

        # Other lightweight roles use defaults
        assert config.max_turns_for_role("qa_synthesizer") == 20
        assert config.timeout_for_role("qa_synthesizer") == 600

        # Unknown roles use global fallback
        assert config.max_turns_for_role("unknown") == 200
        assert config.timeout_for_role("unknown") == 1800  # Still uses default timeout

    def test_merger_timeout_reduced_correctly(self):
        """Merger timeout was reduced from 1200s to 900s (15 min)."""
        config = ExecutionConfig()

        # Merger timeout should be 900s (reduced from 1200s)
        assert config.timeout_for_role("merger") == 900
        assert config.merger_timeout == 900

    def test_all_timeout_reductions_from_architecture_spec(self):
        """All four timeout reductions from architecture C1b are present."""
        config = ExecutionConfig()

        # Architecture C1b specified these reductions:
        # issue_writer: 900→600, qa_synthesizer: 900→600, git: 900→600, merger: 1200→900
        assert config.issue_writer_timeout == 600, "issue_writer timeout should be 600s"
        assert config.qa_synthesizer_timeout == 600, "qa_synthesizer timeout should be 600s"
        assert config.git_timeout == 600, "git timeout should be 600s"
        assert config.merger_timeout == 900, "merger timeout should be 900s"
