"""Integration tests for ExecutionConfig conflict resolution.

Multiple branches modified ExecutionConfig in schemas.py. This test verifies
that all changes were merged correctly without conflicts or lost values.

Priority: Critical - Multiple branches modified the same class
"""

from __future__ import annotations

import pytest

from swe_af.execution.schemas import ExecutionConfig, BuildConfig


class TestSchemaConflictResolution:
    """Verify all ExecutionConfig changes from multiple branches are present."""

    def test_all_per_role_turn_fields_exist(self):
        """All 16 per-role turn fields exist after merge."""
        config = ExecutionConfig()

        expected_turn_fields = [
            "pm_turns",
            "architect_turns",
            "tech_lead_turns",
            "sprint_planner_turns",
            "issue_writer_turns",
            "coder_turns",
            "qa_turns",
            "code_reviewer_turns",
            "qa_synthesizer_turns",
            "issue_advisor_turns",
            "replan_turns",
            "verifier_turns",
            "retry_advisor_turns",
            "git_turns",
            "merger_turns",
            "integration_tester_turns",
        ]

        for field in expected_turn_fields:
            assert hasattr(config, field), f"Missing turn field: {field}"
            value = getattr(config, field)
            assert isinstance(value, int), f"{field} is not an int: {value}"
            assert value > 0, f"{field} has invalid value: {value}"

    def test_all_per_role_timeout_fields_exist(self):
        """All 16 per-role timeout fields exist after merge."""
        config = ExecutionConfig()

        expected_timeout_fields = [
            "pm_timeout",
            "architect_timeout",
            "tech_lead_timeout",
            "sprint_planner_timeout",
            "issue_writer_timeout",
            "coder_timeout",
            "qa_timeout",
            "code_reviewer_timeout",
            "qa_synthesizer_timeout",
            "issue_advisor_timeout",
            "replan_timeout",
            "verifier_timeout",
            "retry_advisor_timeout",
            "git_timeout",
            "merger_timeout",
            "integration_tester_timeout",
        ]

        for field in expected_timeout_fields:
            assert hasattr(config, field), f"Missing timeout field: {field}"
            value = getattr(config, field)
            assert isinstance(value, int), f"{field} is not an int: {value}"
            assert value > 0, f"{field} has invalid value: {value}"

    def test_turn_budget_values_match_expected_reductions(self):
        """Turn budget reductions from issue/00-fix-turn-budgets are correct."""
        config = ExecutionConfig()

        # Values from issue/00-fix-turn-budgets
        expected_values = {
            "git_turns": 20,
            "issue_writer_turns": 25,
            "qa_synthesizer_turns": 20,
            "sprint_planner_turns": 40,
        }

        for field, expected in expected_values.items():
            actual = getattr(config, field)
            assert actual == expected, (
                f"{field} mismatch: expected {expected}, got {actual}"
            )

    def test_timeout_values_match_expected_reductions(self):
        """Timeout reductions from issue/00-fix-timeouts are correct."""
        config = ExecutionConfig()

        # Values from issue/00-fix-timeouts (architecture C1b)
        expected_values = {
            "issue_writer_timeout": 600,
            "qa_synthesizer_timeout": 600,
            "git_timeout": 600,
            "merger_timeout": 900,
        }

        for field, expected in expected_values.items():
            actual = getattr(config, field)
            assert actual == expected, (
                f"{field} mismatch: expected {expected}, got {actual}"
            )

    def test_unchanged_fields_preserved_after_merge(self):
        """Fields not modified by any branch are preserved."""
        config = ExecutionConfig()

        # These were not modified by the merged branches
        assert config.coder_turns == 100, "Coder turns should be unchanged at 100"
        assert config.qa_turns == 75, "QA turns should be unchanged at 75"
        assert config.code_reviewer_turns == 75, "Code reviewer turns should be unchanged at 75"

        assert config.coder_timeout == 1800, "Coder timeout should be unchanged at 1800s"
        assert config.qa_timeout == 1500, "QA timeout should be unchanged at 1500s"

    def test_global_defaults_preserved(self):
        """Global agent_max_turns and agent_timeout_seconds defaults preserved."""
        config = ExecutionConfig()

        assert config.agent_max_turns == 150, "Global default should be 150 turns"
        assert config.agent_timeout_seconds == 1800, "Global default should be 1800s"

    def test_max_advisor_invocations_field_exists(self):
        """max_advisor_invocations field exists (from advisor gate validation)."""
        config = ExecutionConfig()

        assert hasattr(config, "max_advisor_invocations")
        assert config.max_advisor_invocations == 2

    def test_max_replans_field_exists(self):
        """max_replans field exists (from replanner gate validation)."""
        config = ExecutionConfig()

        assert hasattr(config, "max_replans")
        assert config.max_replans == 2

    def test_enable_replanning_field_exists(self):
        """enable_replanning field exists (from replanner gate validation)."""
        config = ExecutionConfig()

        assert hasattr(config, "enable_replanning")
        assert isinstance(config.enable_replanning, bool)

    def test_max_coding_iterations_field_exists(self):
        """max_coding_iterations field exists."""
        config = ExecutionConfig()

        assert hasattr(config, "max_coding_iterations")
        assert config.max_coding_iterations == 6

    def test_accessor_methods_exist_and_work(self):
        """Both accessor methods (max_turns_for_role, timeout_for_role) exist and work."""
        config = ExecutionConfig()

        assert hasattr(config, "max_turns_for_role")
        assert callable(config.max_turns_for_role)

        assert hasattr(config, "timeout_for_role")
        assert callable(config.timeout_for_role)

        # Test they return correct values
        assert config.max_turns_for_role("git") == 20
        assert config.timeout_for_role("git") == 600

    def test_no_duplicate_field_definitions(self):
        """No duplicate field definitions in ExecutionConfig."""
        config = ExecutionConfig()

        # Get all attributes
        attrs = dir(config)

        # Check for duplicate-looking attributes (e.g., git_turns and git_turns_)
        turn_fields = [a for a in attrs if a.endswith("_turns")]
        timeout_fields = [a for a in attrs if a.endswith("_timeout")]

        # Should have exactly 16 of each
        assert len(turn_fields) == 16, f"Expected 16 turn fields, got {len(turn_fields)}: {turn_fields}"
        assert len(timeout_fields) == 16, f"Expected 16 timeout fields, got {len(timeout_fields)}: {timeout_fields}"

    def test_build_config_to_execution_config_dict_complete(self):
        """BuildConfig.to_execution_config_dict() includes all necessary fields."""
        build_config = BuildConfig()
        exec_dict = build_config.to_execution_config_dict()

        # Should include these fields
        required_fields = [
            "runtime",
            "models",
            "max_retries_per_issue",
            "max_replans",
            "enable_replanning",
            "max_integration_test_retries",
            "enable_integration_testing",
            "max_coding_iterations",
            "agent_max_turns",
            "agent_timeout_seconds",
            "max_advisor_invocations",
            "enable_issue_advisor",
            "enable_learning",
        ]

        for field in required_fields:
            assert field in exec_dict, f"Missing field in to_execution_config_dict: {field}"

    def test_pydantic_validation_works(self):
        """Pydantic validation works (no schema errors from merge conflicts)."""
        # Should not raise
        config = ExecutionConfig()

        # Should allow valid overrides
        config2 = ExecutionConfig(
            git_turns=15,
            git_timeout=300,
            agent_max_turns=200,
        )

        assert config2.git_turns == 15
        assert config2.git_timeout == 300
        assert config2.agent_max_turns == 200

    def test_no_hardcoded_constant_conflicts(self):
        """No conflicting hardcoded constants in schemas.py."""
        # The DEFAULT_AGENT_TIMEOUT_SECONDS constant should exist and be reasonable
        from swe_af.execution.schemas import DEFAULT_AGENT_TIMEOUT_SECONDS

        assert DEFAULT_AGENT_TIMEOUT_SECONDS == 2700, (
            f"DEFAULT_AGENT_TIMEOUT_SECONDS should be 2700, got {DEFAULT_AGENT_TIMEOUT_SECONDS}"
        )

    def test_model_config_extra_forbid_preserved(self):
        """ExecutionConfig still has extra='forbid' (prevents typos)."""
        config = ExecutionConfig()

        # Should raise on invalid field
        with pytest.raises(Exception):  # Pydantic ValidationError
            ExecutionConfig(invalid_field=123)

    def test_runtime_models_resolution_works(self):
        """Model resolution from runtime config works after merge."""
        config = ExecutionConfig(runtime="claude_code")

        # Should have model properties
        assert hasattr(config, "git_model")
        assert hasattr(config, "qa_synthesizer_model")
        assert hasattr(config, "issue_writer_model")
        assert hasattr(config, "sprint_planner_model")
        assert hasattr(config, "merger_model")

        # Lightweight roles should use haiku
        assert config.git_model == "haiku"
        assert config.qa_synthesizer_model == "haiku"
        assert config.issue_writer_model == "haiku"
        assert config.sprint_planner_model == "haiku"
        assert config.merger_model == "haiku"

        # Heavy roles should use sonnet
        assert config.coder_model == "sonnet"
        assert config.code_reviewer_model == "sonnet"
