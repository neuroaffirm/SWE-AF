"""Functional tests for compressed verifier.py prompt."""
import subprocess
import sys
from pathlib import Path

import pytest

# Import verifier module directly to avoid circular import issues
verifier_path = Path(__file__).parent.parent / "swe_af" / "prompts" / "verifier.py"
import importlib.util
spec = importlib.util.spec_from_file_location("verifier", verifier_path)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)

SYSTEM_PROMPT = verifier.SYSTEM_PROMPT
verifier_task_prompt = verifier.verifier_task_prompt


def test_verifier_loc_within_target():
    """AC1: verifier.py reduced from 216 to ≤173 LOC (20% reduction)."""
    verifier_path = Path(__file__).parent.parent / "swe_af" / "prompts" / "verifier.py"
    result = subprocess.run(
        ["wc", "-l", str(verifier_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    loc_count = int(result.stdout.strip().split()[0])
    assert loc_count <= 173, f"verifier.py has {loc_count} LOC, expected ≤173"


def test_verification_checklist_preserved():
    """AC2: Verification checklist logic preserved (lines 20-25 in compressed)."""
    # Key verification steps must be present in SYSTEM_PROMPT
    required_steps = [
        "Find responsible issue",
        "Inspect code",
        "build check",
        "Spot-check tests",
        "Record evidence",
    ]
    for step in required_steps:
        assert step.lower() in SYSTEM_PROMPT.lower(), f"Missing verification step: {step}"


def test_ac_validation_rules_maintained():
    """AC3: AC validation rules maintained (lines 27-30 in compressed)."""
    # Judgment standards must be present
    assert "PASS" in SYSTEM_PROMPT, "Missing PASS judgment standard"
    assert "FAIL" in SYSTEM_PROMPT, "Missing FAIL judgment standard"
    assert "NO partial" in SYSTEM_PROMPT or "no partial" in SYSTEM_PROMPT.lower(), "Missing 'no partial' rule"


def test_pass_fail_decision_criteria_intact():
    """AC4: Pass/fail decision criteria intact (line 43 in compressed)."""
    # Overall verdict logic must be preserved
    assert "`passed = true`" in SYSTEM_PROMPT or "passed = true" in SYSTEM_PROMPT, "Missing pass verdict logic"
    assert "ALL must-have" in SYSTEM_PROMPT or "all must-have" in SYSTEM_PROMPT.lower(), "Missing ALL criteria requirement"


def test_test_coverage_assessment_preserved():
    """AC5: Test coverage assessment guidelines preserved (line 24 in compressed)."""
    # Test execution guidance must be present
    assert "test" in SYSTEM_PROMPT.lower(), "Missing test guidance"
    assert "Spot-check" in SYSTEM_PROMPT or "spot-check" in SYSTEM_PROMPT.lower(), "Missing spot-check guidance"


def test_verifier_task_prompt_structure():
    """Functional test: verifier_task_prompt generates complete prompt."""
    prd = {
        "validated_description": "Test PRD",
        "acceptance_criteria": ["AC1: Feature works", "AC2: Tests pass"],
        "must_have": ["Must have 1"],
        "nice_to_have": ["Nice to have 1"],
    }
    completed_issues = [
        {
            "issue_name": "test-issue",
            "result_summary": "Completed successfully",
            "files_changed": ["test.py"],
        }
    ]
    failed_issues = []
    skipped_issues = []
    build_health = {
        "issues_completed": 1,
        "issues_failed": 0,
        "total_tests_reported": 5,
        "modules_passing": ["module1"],
        "modules_failing": [],
        "known_risks": [],
    }

    prompt = verifier_task_prompt(
        prd=prd,
        artifacts_dir="/test/artifacts",
        completed_issues=completed_issues,
        failed_issues=failed_issues,
        skipped_issues=skipped_issues,
        build_health=build_health,
    )

    # Verify all key sections are present
    assert "Product Requirements Document" in prompt
    assert "Acceptance Criteria" in prompt
    assert "AC1: Feature works" in prompt
    assert "AC2: Tests pass" in prompt
    assert "Build Health Dashboard" in prompt
    assert "Completed Issues" in prompt
    assert "test-issue" in prompt
    assert "Your Task" in prompt
    assert "VerificationResult" in prompt


def test_verifier_task_prompt_empty_cases():
    """Edge case: Empty AC list, missing build_health."""
    prd = {
        "validated_description": "Test PRD with no ACs",
        "acceptance_criteria": [],
    }
    completed_issues = []
    failed_issues = []
    skipped_issues = []

    prompt = verifier_task_prompt(
        prd=prd,
        artifacts_dir="/test/artifacts",
        completed_issues=completed_issues,
        failed_issues=failed_issues,
        skipped_issues=skipped_issues,
        build_health=None,
    )

    # Should handle empty cases gracefully
    assert "(none specified)" in prompt or "(none)" in prompt
    assert "Product Requirements Document" in prompt
    assert "Your Task" in prompt


def test_verifier_task_prompt_all_failed_build():
    """Edge case: All issues failed."""
    prd = {
        "validated_description": "Failed build",
        "acceptance_criteria": ["AC1: Should work"],
    }
    completed_issues = []
    failed_issues = [
        {
            "issue_name": "failed-issue",
            "error_message": "Compilation error",
        }
    ]
    skipped_issues = ["skipped-issue"]

    prompt = verifier_task_prompt(
        prd=prd,
        artifacts_dir="/test/artifacts",
        completed_issues=completed_issues,
        failed_issues=failed_issues,
        skipped_issues=skipped_issues,
        build_health=None,
    )

    # Should show failed issues clearly
    assert "Failed Issues" in prompt
    assert "failed-issue" in prompt
    assert "FAILED" in prompt
    assert "Compilation error" in prompt
    assert "Skipped Issues" in prompt
    assert "skipped-issue" in prompt


def test_system_prompt_contains_tools():
    """Verify Tools section is preserved."""
    assert "READ" in SYSTEM_PROMPT, "Missing READ tool"
    assert "GLOB" in SYSTEM_PROMPT, "Missing GLOB tool"
    assert "GREP" in SYSTEM_PROMPT, "Missing GREP tool"
    assert "BASH" in SYSTEM_PROMPT, "Missing BASH tool"


def test_system_prompt_contains_constraints():
    """Verify Constraints section is preserved."""
    assert "Do NOT modify" in SYSTEM_PROMPT, "Missing 'do not modify' constraint"
    assert "verify, not fix" in SYSTEM_PROMPT or "verifier, not a fixer" in SYSTEM_PROMPT.lower(), "Missing verify-not-fix constraint"


def test_evidence_requirements_preserved():
    """Verify Evidence Requirements section is preserved."""
    assert "Evidence Requirements" in SYSTEM_PROMPT or "evidence" in SYSTEM_PROMPT.lower(), "Missing evidence guidance"
    assert "specific" in SYSTEM_PROMPT.lower(), "Missing specificity requirement"


def test_repository_presentation_preserved():
    """Verify Repository Presentation section is preserved."""
    assert "Repository Presentation" in SYSTEM_PROMPT or ".gitignore" in SYSTEM_PROMPT, "Missing repository presentation section"
    assert "git status" in SYSTEM_PROMPT, "Missing git status check"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
