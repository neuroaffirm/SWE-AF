"""Integration test for compressed prompts token count.

Verifies that the total system prompt tokens across all 15 agents meets
the acceptance criteria target of ≤6800 tokens after compression.

Priority: High - This is a direct AC for the prompt compression feature

Note: This test reads prompt files directly to avoid circular import issues
in the swe_af.prompts package.
"""

from __future__ import annotations

import ast
import pytest
import tiktoken
from pathlib import Path


class TestPromptTokenCount:
    """Verify compressed prompts meet token count targets."""

    def _extract_system_prompt_from_file(self, filepath: Path) -> str:
        """Extract SYSTEM_PROMPT value from a Python file using AST parsing."""
        with open(filepath, 'r') as f:
            source = f.read()

        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'SYSTEM_PROMPT':
                        if isinstance(node.value, ast.Constant):
                            return node.value.value

        raise ValueError(f"No SYSTEM_PROMPT found in {filepath}")

    def test_total_system_prompt_tokens_under_acceptance_criteria_target(self):
        """Total system prompt tokens across all 15 agents meets AC target ≤6800."""
        enc = tiktoken.get_encoding("cl100k_base")

        prompts_dir = Path("/workspaces/SWE-AF/workspace/SWE-AF/swe_af/prompts")

        prompt_files = [
            "coder.py",
            "code_reviewer.py",
            "qa.py",
            "qa_synthesizer.py",
            "issue_advisor.py",
            "replanner.py",
            "verifier.py",
            "architect.py",
            "product_manager.py",
            "tech_lead.py",
            "sprint_planner.py",
            "issue_writer.py",
            "git_init.py",
            "merger.py",
            "integration_tester.py",
        ]

        total_tokens = 0
        individual_tokens = {}

        for filename in prompt_files:
            filepath = prompts_dir / filename
            prompt = self._extract_system_prompt_from_file(filepath)

            tokens = len(enc.encode(prompt))
            name = filename.replace(".py", "")
            individual_tokens[name] = tokens
            total_tokens += tokens

        # Acceptance criteria: total_tokens <= 6800
        assert total_tokens <= 6800, (
            f"Total system prompt tokens {total_tokens} exceeds target 6800. "
            f"Individual counts: {individual_tokens}"
        )

    def test_all_15_prompts_exist_and_are_non_empty(self):
        """All 15 system prompts exist and are non-empty after compression."""
        prompts_dir = Path("/workspaces/SWE-AF/workspace/SWE-AF/swe_af/prompts")

        prompt_files = [
            "coder.py",
            "code_reviewer.py",
            "qa.py",
            "qa_synthesizer.py",
            "issue_advisor.py",
            "replanner.py",
            "verifier.py",
            "architect.py",
            "product_manager.py",
            "tech_lead.py",
            "sprint_planner.py",
            "issue_writer.py",
            "git_init.py",
            "merger.py",
            "integration_tester.py",
        ]

        for filename in prompt_files:
            filepath = prompts_dir / filename
            prompt = self._extract_system_prompt_from_file(filepath)

            name = filename.replace(".py", "")
            assert isinstance(prompt, str), f"{name} prompt is not a string"
            assert len(prompt) > 50, f"{name} prompt is too short ({len(prompt)} chars)"
            assert len(prompt.split()) >= 20, f"{name} prompt has too few words"

    def test_lightweight_agents_have_small_token_counts(self):
        """Lightweight agents (git, issue_writer, qa_synthesizer) have compressed prompts."""
        enc = tiktoken.get_encoding("cl100k_base")
        prompts_dir = Path("/workspaces/SWE-AF/workspace/SWE-AF/swe_af/prompts")

        lightweight_files = [
            "git_init.py",
            "issue_writer.py",
            "qa_synthesizer.py",
        ]

        for filename in lightweight_files:
            filepath = prompts_dir / filename
            prompt = self._extract_system_prompt_from_file(filepath)

            tokens = len(enc.encode(prompt))
            name = filename.replace(".py", "")

            # Lightweight agents should have <500 tokens after compression
            assert tokens < 500, (
                f"{name} has {tokens} tokens, should be compressed to <500 for lightweight agent"
            )

    def test_critical_keywords_preserved_in_lightweight_prompts(self):
        """Critical keywords preserved in lightweight agent prompts after compression."""
        prompts_dir = Path("/workspaces/SWE-AF/workspace/SWE-AF/swe_af/prompts")

        git_init_prompt = self._extract_system_prompt_from_file(prompts_dir / "git_init.py")
        issue_writer_prompt = self._extract_system_prompt_from_file(prompts_dir / "issue_writer.py")
        qa_synthesizer_prompt = self._extract_system_prompt_from_file(prompts_dir / "qa_synthesizer.py")

        # Git init must have init/branch concepts
        assert "git" in git_init_prompt.lower()
        assert "branch" in git_init_prompt.lower()

        # Issue writer must have issue/AC concepts
        assert "issue" in issue_writer_prompt.lower()
        assert "acceptance" in issue_writer_prompt.lower() or "criteria" in issue_writer_prompt.lower()

        # QA synthesizer must have fix/approve/block actions
        assert "fix" in qa_synthesizer_prompt.lower()
        assert "approve" in qa_synthesizer_prompt.lower()
