"""Tests for atomic PRD write in Product Manager.

Covers acceptance criteria:
- AC1: PM writes PRD to temp file using tempfile.mkstemp()
- AC2: Temp file created in same directory as final PRD path
- AC3: Atomic rename via shutil.move() replaces final PRD file
- AC4: Exception handling cleans up temp file on write failure
- AC5: Existing PRD write behavior preserved for non-concurrent flows
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock, Mock

import pytest

from swe_af.reasoners.schemas import PRD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def _make_valid_prd():
    """Create a valid PRD object."""
    return PRD(
        validated_description="Test PRD for atomic write",
        acceptance_criteria=["AC-1: Feature works"],
        must_have=["Feature X"],
        nice_to_have=[],
        out_of_scope=[],
        assumptions=["Assumption 1"],
        risks=["Risk 1"],
    )


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------

def test_temp_file_creation_and_atomic_rename(tmp_path):
    """AC1, AC2, AC3: Verify temp file is created in same dir and atomically renamed.

    This test verifies that:
    1. A temp file is created using tempfile.mkstemp()
    2. The temp file is in the same directory as the final PRD
    3. The atomic rename happens via shutil.move()
    """
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    artifacts_dir = ".artifacts"
    prd_dir = repo_path / artifacts_dir / "plan"
    prd_dir.mkdir(parents=True)
    prd_path = prd_dir / "prd.md"

    # Write initial PRD content (simulating what the PM agent would do)
    initial_content = "# PRD\n\nTest content for atomic write"
    prd_path.write_text(initial_content)

    # Mock AgentAI to return a valid PRD without actually running
    mock_response = MagicMock()
    mock_response.parsed = _make_valid_prd()

    # Create a mock router with note method
    mock_router = Mock()
    mock_router.note = Mock()

    # Patch at import time
    with patch("swe_af.reasoners.pipeline.router", mock_router), \
         patch("swe_af.reasoners.pipeline.AgentAI") as mock_ai_class:
        mock_ai = MagicMock()
        mock_ai.run = AsyncMock(return_value=mock_response)
        mock_ai_class.return_value = mock_ai

        # Track calls to tempfile.mkstemp and shutil.move
        with patch("tempfile.mkstemp") as mock_mkstemp, \
             patch("shutil.move") as mock_move:

            # Set up mock tempfile
            temp_fd = 999
            temp_path = str(prd_dir / ".prd_test.md.tmp")
            mock_mkstemp.return_value = (temp_fd, temp_path)

            # Mock os.fdopen to return a writable file-like object
            mock_file = MagicMock()
            mock_file.__enter__ = MagicMock(return_value=mock_file)
            mock_file.__exit__ = MagicMock(return_value=False)

            with patch("os.fdopen", return_value=mock_file):
                # Import after patching
                from swe_af.reasoners.pipeline import run_product_manager

                # Run the PM
                result = _run(run_product_manager(
                    goal="Test goal",
                    repo_path=str(repo_path),
                    artifacts_dir=artifacts_dir,
                ))

            # Verify mkstemp was called with correct directory
            mock_mkstemp.assert_called_once()
            call_kwargs = mock_mkstemp.call_args[1]
            assert call_kwargs["dir"] == str(prd_dir), "Temp file should be in same dir as PRD"
            assert call_kwargs["prefix"] == ".prd_"
            assert call_kwargs["suffix"] == ".md.tmp"

            # Verify shutil.move was called for atomic rename
            mock_move.assert_called_once_with(temp_path, str(prd_path))

    # Verify the result is valid
    assert result is not None
    assert "validated_description" in result


def test_exception_handling_cleans_temp_file(tmp_path):
    """AC4: Verify temp file is cleaned up on write failure."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    artifacts_dir = ".artifacts"
    prd_dir = repo_path / artifacts_dir / "plan"
    prd_dir.mkdir(parents=True)
    prd_path = prd_dir / "prd.md"

    # Write initial PRD content
    prd_path.write_text("# PRD\n\nTest content")

    # Mock AgentAI
    mock_response = MagicMock()
    mock_response.parsed = _make_valid_prd()

    # Create a mock router
    mock_router = Mock()
    mock_router.note = Mock()

    with patch("swe_af.reasoners.pipeline.router", mock_router), \
         patch("swe_af.reasoners.pipeline.AgentAI") as mock_ai_class:
        mock_ai = MagicMock()
        mock_ai.run = AsyncMock(return_value=mock_response)
        mock_ai_class.return_value = mock_ai

        # Track temp file cleanup
        with patch("tempfile.mkstemp") as mock_mkstemp, \
             patch("shutil.move") as mock_move, \
             patch("os.unlink") as mock_unlink, \
             patch("os.path.exists") as mock_exists:

            temp_fd = 999
            temp_path = str(prd_dir / ".prd_test.md.tmp")
            mock_mkstemp.return_value = (temp_fd, temp_path)
            mock_exists.return_value = True

            # Make shutil.move raise an exception
            mock_move.side_effect = OSError("Simulated write failure")

            # Mock os.fdopen
            mock_file = MagicMock()
            mock_file.__enter__ = MagicMock(return_value=mock_file)
            mock_file.__exit__ = MagicMock(return_value=False)

            with patch("os.fdopen", return_value=mock_file):
                # Import after patching
                from swe_af.reasoners.pipeline import run_product_manager

                # Run the PM - should not raise, but log warning
                result = _run(run_product_manager(
                    goal="Test goal",
                    repo_path=str(repo_path),
                    artifacts_dir=artifacts_dir,
                ))

            # Verify temp file cleanup was attempted
            mock_unlink.assert_called_once_with(temp_path)

    # Should still return valid result even if atomic write fails
    assert result is not None


def test_preserves_existing_behavior_when_no_file(tmp_path):
    """AC5: Verify existing PRD write behavior preserved when PM agent doesn't write file."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    artifacts_dir = ".artifacts"

    # Mock AgentAI to return a valid PRD
    mock_response = MagicMock()
    mock_response.parsed = _make_valid_prd()

    # Create a mock router
    mock_router = Mock()
    mock_router.note = Mock()

    with patch("swe_af.reasoners.pipeline.router", mock_router), \
         patch("swe_af.reasoners.pipeline.AgentAI") as mock_ai_class:
        mock_ai = MagicMock()
        mock_ai.run = AsyncMock(return_value=mock_response)
        mock_ai_class.return_value = mock_ai

        # Import after patching
        from swe_af.reasoners.pipeline import run_product_manager

        # Run the PM - no PRD file exists
        result = _run(run_product_manager(
            goal="Test goal",
            repo_path=str(repo_path),
            artifacts_dir=artifacts_dir,
        ))

    # Should work normally without atomic write path
    assert result is not None
    assert "validated_description" in result


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

def test_concurrent_read_no_partial_content(tmp_path):
    """Integration test: Concurrent reads should never see partial PRD content.

    This test simulates the PM-Architect parallelization scenario where:
    - PM writes PRD atomically
    - Architect polls and reads PRD concurrently
    - Architect should never see partial content
    """
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    artifacts_dir = ".artifacts"
    prd_dir = repo_path / artifacts_dir / "plan"
    prd_dir.mkdir(parents=True)
    prd_path = prd_dir / "prd.md"

    # Full PRD content that will be written
    full_prd_content = "# PRD\n\n" + ("Line of content\n" * 1000)
    partial_reads = []
    read_thread_running = threading.Event()
    stop_reading = threading.Event()

    def concurrent_reader():
        """Continuously read PRD file and check for partial content."""
        read_thread_running.set()
        while not stop_reading.is_set():
            if prd_path.exists():
                try:
                    content = prd_path.read_text()
                    # If we can read it, it should be complete
                    if content and content != full_prd_content:
                        partial_reads.append(content)
                except Exception:
                    # File might be mid-operation, skip this read
                    pass
            time.sleep(0.001)  # High-frequency polling

    # Start concurrent reader thread
    reader_thread = threading.Thread(target=concurrent_reader)
    reader_thread.start()

    # Wait for reader to start
    read_thread_running.wait(timeout=1.0)

    # Write initial content (simulating PM agent write)
    prd_path.write_text(full_prd_content)

    # Mock AgentAI
    mock_response = MagicMock()
    mock_response.parsed = _make_valid_prd()

    # Create a mock router
    mock_router = Mock()
    mock_router.note = Mock()

    with patch("swe_af.reasoners.pipeline.router", mock_router), \
         patch("swe_af.reasoners.pipeline.AgentAI") as mock_ai_class:
        mock_ai = MagicMock()
        mock_ai.run = AsyncMock(return_value=mock_response)
        mock_ai_class.return_value = mock_ai

        # Import after patching
        from swe_af.reasoners.pipeline import run_product_manager

        # Run PM (this will do the atomic rewrite)
        _run(run_product_manager(
            goal="Test goal",
            repo_path=str(repo_path),
            artifacts_dir=artifacts_dir,
        ))

    # Stop reader and wait for it to finish
    time.sleep(0.1)  # Let reader do a few more reads
    stop_reading.set()
    reader_thread.join(timeout=2.0)

    # Verify no partial reads occurred
    assert len(partial_reads) == 0, \
        f"Found {len(partial_reads)} partial reads! Atomic write failed."

    # Verify final content is correct
    assert prd_path.read_text() == full_prd_content


def test_prd_write_with_unicode_content(tmp_path):
    """Verify atomic write handles unicode content correctly."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    artifacts_dir = ".artifacts"
    prd_dir = repo_path / artifacts_dir / "plan"
    prd_dir.mkdir(parents=True)
    prd_path = prd_dir / "prd.md"

    # Unicode content with various characters
    unicode_content = "# PRD\n\n测试内容 тест содержание ทดสอบเนื้อหา 🚀 ✨"
    prd_path.write_text(unicode_content, encoding='utf-8')

    # Mock AgentAI
    mock_response = MagicMock()
    mock_response.parsed = _make_valid_prd()

    # Create a mock router
    mock_router = Mock()
    mock_router.note = Mock()

    with patch("swe_af.reasoners.pipeline.router", mock_router), \
         patch("swe_af.reasoners.pipeline.AgentAI") as mock_ai_class:
        mock_ai = MagicMock()
        mock_ai.run = AsyncMock(return_value=mock_response)
        mock_ai_class.return_value = mock_ai

        # Import after patching
        from swe_af.reasoners.pipeline import run_product_manager

        # Run PM
        result = _run(run_product_manager(
            goal="Test goal with unicode",
            repo_path=str(repo_path),
            artifacts_dir=artifacts_dir,
        ))

    # Verify result is valid
    assert result is not None

    # Verify content was preserved correctly
    final_content = prd_path.read_text(encoding='utf-8')
    assert final_content == unicode_content
