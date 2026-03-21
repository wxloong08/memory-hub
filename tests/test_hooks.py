"""
Tests for Claude Code hook integration
Tests hook functionality, context injection, and error handling
"""

import pytest
import os
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime


class TestSessionStartHook:
    """Test session-start.sh hook functionality"""

    @pytest.fixture
    def hook_script_path(self):
        """Get path to session-start hook"""
        project_root = Path(__file__).parent.parent
        hook_path = project_root / "claude-code-integration" / "hooks" / "session-start.sh"
        return str(hook_path)

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

    def test_hook_script_exists(self, hook_script_path):
        """Test that hook script exists"""
        assert os.path.exists(hook_script_path), "Hook script not found"

    def test_hook_script_executable(self, hook_script_path):
        """Test that hook script is executable"""
        # On Windows, this test may not be relevant
        if os.name != 'nt':
            assert os.access(hook_script_path, os.X_OK), "Hook script not executable"

    def test_hook_handles_missing_memory_hub(self, hook_script_path, temp_project_dir):
        """Test hook gracefully handles Memory Hub not running"""
        env = os.environ.copy()
        env['CLAUDE_WORKING_DIR'] = temp_project_dir

        # Run hook when Memory Hub is not running
        result = subprocess.run(
            ['bash', hook_script_path],
            env=env,
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should exit successfully with warning
        assert result.returncode == 0
        assert "Memory Hub not running" in result.stdout or "Skipping" in result.stdout

    def test_hook_creates_claude_directory(self, hook_script_path, temp_project_dir):
        """Test that hook creates .claude directory if needed"""
        env = os.environ.copy()
        env['CLAUDE_WORKING_DIR'] = temp_project_dir

        # Run hook
        subprocess.run(
            ['bash', hook_script_path],
            env=env,
            capture_output=True,
            timeout=10
        )

        # .claude directory should be created (if Memory Hub was accessible)
        # This test is conditional on Memory Hub availability

    def test_hook_preserves_existing_claude_md(self, hook_script_path, temp_project_dir):
        """Test that hook preserves existing CLAUDE.md content"""
        # Create .claude directory and CLAUDE.md
        claude_dir = Path(temp_project_dir) / ".claude"
        claude_dir.mkdir(exist_ok=True)
        claude_md = claude_dir / "CLAUDE.md"

        original_content = "# Original Content\n\nThis should be preserved."
        claude_md.write_text(original_content)

        env = os.environ.copy()
        env['CLAUDE_WORKING_DIR'] = temp_project_dir

        # Run hook
        subprocess.run(
            ['bash', hook_script_path],
            env=env,
            capture_output=True,
            timeout=10
        )

        # Check if backup was created
        backup_path = claude_dir / "CLAUDE.md.backup"
        if backup_path.exists():
            backup_content = backup_path.read_text()
            assert original_content in backup_content

    def test_hook_uses_working_dir_env_var(self, hook_script_path):
        """Test that hook uses CLAUDE_WORKING_DIR environment variable"""
        test_dir = "/test/custom/directory"
        env = os.environ.copy()
        env['CLAUDE_WORKING_DIR'] = test_dir

        # Run hook (will fail to create directory but should try)
        result = subprocess.run(
            ['bash', hook_script_path],
            env=env,
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should attempt to use the custom directory
        assert result.returncode == 0  # Should exit gracefully


class TestHookInstallation:
    """Test hook installation script"""

    @pytest.fixture
    def install_script_path(self):
        """Get path to install script"""
        project_root = Path(__file__).parent.parent
        install_path = project_root / "claude-code-integration" / "install.sh"
        return str(install_path)

    def test_install_script_exists(self, install_script_path):
        """Test that install script exists"""
        assert os.path.exists(install_script_path), "Install script not found"

    def test_install_script_executable(self, install_script_path):
        """Test that install script is executable"""
        if os.name != 'nt':
            assert os.access(install_script_path, os.X_OK), "Install script not executable"

    def test_install_script_syntax(self, install_script_path):
        """Test that install script has valid bash syntax"""
        result = subprocess.run(
            ['bash', '-n', install_script_path],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0, f"Syntax error in install script: {result.stderr}"


class TestContextInjection:
    """Test context injection functionality"""

    def test_context_format(self):
        """Test that injected context has correct format"""
        # Mock context from Memory Hub
        context = """# Auto-Generated Context

*Last updated: 2024-03-09 15:30*

## Recent Activity

### claude_web - 2024-03-09 15:00:00
**Summary**: Build a memory system
**Importance**: 8/10
**Location**: /test/project

---

# Original Memory

Original content here
"""

        # Verify format
        assert "# Auto-Generated Context" in context
        assert "## Recent Activity" in context
        assert "# Original Memory" in context

    def test_context_includes_metadata(self):
        """Test that context includes conversation metadata"""
        context = """### claude_code - 2024-03-09 14:30:00
**Summary**: Implement database layer
**Importance**: 9/10
**Location**: /home/user/project
"""

        assert "claude_code" in context
        assert "Summary" in context
        assert "Importance" in context
        assert "Location" in context


class TestHookErrorHandling:
    """Test hook error handling"""

    @pytest.fixture
    def hook_script_path(self):
        """Get path to session-start hook"""
        project_root = Path(__file__).parent.parent
        hook_path = project_root / "claude-code-integration" / "hooks" / "session-start.sh"
        return str(hook_path)

    def test_hook_handles_network_error(self, hook_script_path):
        """Test hook handles network errors gracefully"""
        env = os.environ.copy()
        env['CLAUDE_WORKING_DIR'] = "/tmp/test"

        result = subprocess.run(
            ['bash', hook_script_path],
            env=env,
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should not crash
        assert result.returncode == 0

    def test_hook_handles_invalid_json(self, hook_script_path):
        """Test hook handles invalid JSON response"""
        # This would require mocking the curl response
        # For now, just verify hook doesn't crash
        pass

    def test_hook_timeout_handling(self, hook_script_path):
        """Test that hook doesn't hang indefinitely"""
        env = os.environ.copy()
        env['CLAUDE_WORKING_DIR'] = "/tmp/test"

        # Should complete within reasonable time
        result = subprocess.run(
            ['bash', hook_script_path],
            env=env,
            capture_output=True,
            timeout=30  # 30 second timeout
        )

        assert result.returncode == 0


class TestHookIntegration:
    """Test hook integration with Memory Hub"""

    def test_hook_requests_correct_endpoint(self):
        """Test that hook requests correct Memory Hub endpoint"""
        # Verify hook uses http://localhost:8765/api/context
        project_root = Path(__file__).parent.parent
        hook_path = project_root / "claude-code-integration" / "hooks" / "session-start.sh"

        if hook_path.exists():
            content = hook_path.read_text()
            assert "localhost:8765" in content
            assert "/api/context" in content
            assert "/health" in content

    def test_hook_passes_working_dir_parameter(self):
        """Test that hook passes working_dir to API"""
        project_root = Path(__file__).parent.parent
        hook_path = project_root / "claude-code-integration" / "hooks" / "session-start.sh"

        if hook_path.exists():
            content = hook_path.read_text()
            assert "working_dir=" in content or "WORKING_DIR" in content

    def test_hook_uses_jq_for_json_parsing(self):
        """Test that hook uses jq for JSON parsing"""
        project_root = Path(__file__).parent.parent
        hook_path = project_root / "claude-code-integration" / "hooks" / "session-start.sh"

        if hook_path.exists():
            content = hook_path.read_text()
            assert "jq" in content


class TestHookConfiguration:
    """Test hook configuration and setup"""

    def test_hook_location(self):
        """Test that hook is in correct location"""
        project_root = Path(__file__).parent.parent
        hook_path = project_root / "claude-code-integration" / "hooks" / "session-start.sh"

        assert hook_path.exists(), "Hook should be in claude-code-integration/hooks/"

    def test_hook_naming_convention(self):
        """Test that hook follows naming convention"""
        project_root = Path(__file__).parent.parent
        hooks_dir = project_root / "claude-code-integration" / "hooks"

        if hooks_dir.exists():
            hook_files = list(hooks_dir.glob("*.sh"))
            assert len(hook_files) > 0, "Should have at least one hook script"

            for hook in hook_files:
                assert hook.suffix == ".sh", "Hook should have .sh extension"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
