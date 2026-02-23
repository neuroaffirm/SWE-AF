"""Tests for model downgrade to haiku for git, merger, and issue_writer."""

import pytest

from swe_af.execution.schemas import (
    ExecutionConfig,
    resolve_runtime_models,
)


class TestModelDowngrade:
    """Test that git, merger, and issue_writer models default to haiku."""

    def test_git_model_defaults_to_haiku(self) -> None:
        """AC1: _RUNTIME_BASE_MODELS['claude_code'] sets git_model='haiku'."""
        resolved = resolve_runtime_models(runtime="claude_code", models=None)
        assert resolved["git_model"] == "haiku"

    def test_merger_model_defaults_to_haiku(self) -> None:
        """AC2: _RUNTIME_BASE_MODELS['claude_code'] sets merger_model='haiku'."""
        resolved = resolve_runtime_models(runtime="claude_code", models=None)
        assert resolved["merger_model"] == "haiku"

    def test_issue_writer_model_defaults_to_haiku(self) -> None:
        """AC3: _RUNTIME_BASE_MODELS['claude_code'] sets issue_writer_model='haiku'."""
        resolved = resolve_runtime_models(runtime="claude_code", models=None)
        assert resolved["issue_writer_model"] == "haiku"

    def test_qa_synthesizer_model_preserved_as_haiku(self) -> None:
        """AC4: qa_synthesizer_model='haiku' preserved from baseline."""
        resolved = resolve_runtime_models(runtime="claude_code", models=None)
        assert resolved["qa_synthesizer_model"] == "haiku"

    def test_config_override_git_to_sonnet(self) -> None:
        """AC5: Config override via models={'git': 'sonnet'} still functional."""
        resolved = resolve_runtime_models(
            runtime="claude_code", models={"git": "sonnet"}
        )
        assert resolved["git_model"] == "sonnet"

    def test_config_override_merger_to_sonnet(self) -> None:
        """AC5: Config override for merger model."""
        resolved = resolve_runtime_models(
            runtime="claude_code", models={"merger": "sonnet"}
        )
        assert resolved["merger_model"] == "sonnet"

    def test_config_override_issue_writer_to_sonnet(self) -> None:
        """AC5: Config override for issue_writer model."""
        resolved = resolve_runtime_models(
            runtime="claude_code", models={"issue_writer": "sonnet"}
        )
        assert resolved["issue_writer_model"] == "sonnet"

    def test_execution_config_haiku_defaults(self) -> None:
        """Verify ExecutionConfig exposes haiku defaults via properties."""
        cfg = ExecutionConfig(runtime="claude_code")
        assert cfg.git_model == "haiku"
        assert cfg.merger_model == "haiku"
        assert cfg.issue_writer_model == "haiku"
        assert cfg.qa_synthesizer_model == "haiku"

    def test_execution_config_override_works(self) -> None:
        """Verify ExecutionConfig respects model overrides."""
        cfg = ExecutionConfig(
            runtime="claude_code",
            models={
                "git": "sonnet",
                "merger": "opus",
                "issue_writer": "sonnet",
            },
        )
        assert cfg.git_model == "sonnet"
        assert cfg.merger_model == "opus"
        assert cfg.issue_writer_model == "sonnet"

    def test_all_haiku_models_in_claude_code_runtime(self) -> None:
        """Integration test: verify all four haiku models in claude_code."""
        resolved = resolve_runtime_models(runtime="claude_code", models=None)
        haiku_models = [
            "qa_synthesizer_model",
            "git_model",
            "merger_model",
            "issue_writer_model",
        ]
        for model_field in haiku_models:
            assert (
                resolved[model_field] == "haiku"
            ), f"{model_field} should be haiku, got {resolved[model_field]}"
