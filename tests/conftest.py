"""Test configuration with proper isolation from user's home directory."""

import pytest
from pathlib import Path
import sys
import tempfile
import os


# Create a persistent temp directory for all tests in this session
_test_tmp_dir = None
_original_home = None


def pytest_configure(config):
    """Hook that runs before test collection - patch paths early."""
    global _test_tmp_dir, _original_home
    
    # Save original HOME
    _original_home = os.environ.get("HOME")
    
    # Create a persistent temp directory for the entire test session
    _test_tmp_dir = tempfile.mkdtemp(prefix="moa_test_")
    test_moa_home = Path(_test_tmp_dir) / ".moa"
    test_moa_home.mkdir()
    
    # Create subdirectories
    for subdir in ["cache", "debates", "templates", "sessions"]:
        (test_moa_home / subdir).mkdir()
    
    # Set HOME before any imports
    os.environ["HOME"] = _test_tmp_dir
    
    # Patch moa.config before it's imported by test modules
    # We do this by removing it from sys.modules if it's there, then patching when it loads
    if "moa.config" in sys.modules:
        del sys.modules["moa.config"]
    
    # Now import and patch
    import moa.config
    
    # Patch all the paths
    test_global_env = test_moa_home / ".env"
    test_usage_file = test_moa_home / "usage.json"
    test_history_file = test_moa_home / "history.jsonl"
    test_cache_dir = test_moa_home / "cache"
    test_outcomes_file = test_moa_home / "outcomes.jsonl"
    test_templates_dir = test_moa_home / "templates"
    test_health_file = test_moa_home / "health.json"
    
    moa.config.MOA_HOME = test_moa_home
    moa.config.GLOBAL_ENV = test_global_env
    moa.config.USAGE_FILE = test_usage_file
    moa.config.HISTORY_FILE = test_history_file
    moa.config.CACHE_DIR = test_cache_dir
    moa.config.OUTCOMES_FILE = test_outcomes_file
    moa.config.TEMPLATES_DIR = test_templates_dir


def pytest_unconfigure(config):
    """Hook that runs after all tests - cleanup and restore HOME."""
    global _original_home
    if _original_home:
        os.environ["HOME"] = _original_home


@pytest.fixture
def snapshot_real_moa_home():
    """Snapshot the real ~/.moa before tests run, for guard test."""
    real_moa = Path.home() / ".moa"
    if real_moa.exists():
        snapshot = {
            "mtime": real_moa.stat().st_mtime,
            "files": {str(f.relative_to(real_moa)): f.stat().st_mtime 
                     for f in real_moa.rglob("*") if f.is_file()},
        }
    else:
        snapshot = {"exists": False}
    return snapshot


def test_isolation_real_moa_unchanged(snapshot_real_moa_home):
    """Guard test: verify that no test modified the real ~/.moa directory."""
    real_moa = Path.home() / ".moa"
    
    if "exists" in snapshot_real_moa_home and not snapshot_real_moa_home["exists"]:
        # Real ~/.moa didn't exist at start, verify it still doesn't
        assert not real_moa.exists(), "Test suite created real ~/.moa"
    elif real_moa.exists():
        # Real ~/.moa existed, verify nothing was modified
        current_files = {str(f.relative_to(real_moa)): f.stat().st_mtime 
                        for f in real_moa.rglob("*") if f.is_file()}
        original_files = snapshot_real_moa_home.get("files", {})
        
        # Check no new files were created
        new_files = set(current_files.keys()) - set(original_files.keys())
        assert not new_files, f"Tests created new files in ~/.moa: {new_files}"
        
        # Check no files were deleted
        deleted_files = set(original_files.keys()) - set(current_files.keys())
        assert not deleted_files, f"Tests deleted files from ~/.moa: {deleted_files}"
        
        # Check no files were modified (within 1s tolerance for timestamp precision)
        modified_files = [f for f in original_files.keys() 
                         if abs(current_files[f] - original_files[f]) > 1]
        assert not modified_files, f"Tests modified files in ~/.moa: {modified_files}"
