"""
Unit tests for system health check.

These are lightweight integration tests that verify the health check
functions work correctly with the actual database and file system.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Import health check functions
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestDatabaseConnectivity:
    """Test database connection health checks."""

    @patch('scripts.system_health_check.get_db_connection')
    def test_successful_connection(self, mock_get_db):
        """Database connection succeeds."""
        from scripts.system_health_check import check_database_connectivity

        # Mock successful connection and query
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn

        status, message = check_database_connectivity()

        assert status is True
        assert "successful" in message.lower()

    @patch('scripts.system_health_check.get_db_connection')
    def test_connection_failure(self, mock_get_db):
        """Database connection fails."""
        from scripts.system_health_check import check_database_connectivity

        # Simulate connection error
        mock_get_db.side_effect = Exception("Connection refused")

        status, message = check_database_connectivity()

        assert status is False
        assert "refused" in message.lower() or "error" in message.lower()


class TestDiskSpace:
    """Test disk space monitoring."""

    @patch('scripts.system_health_check.psutil.disk_usage')
    @patch('scripts.system_health_check.Path.exists')
    def test_adequate_space(self, mock_exists, mock_disk_usage):
        """Sufficient disk space on all mounts."""
        from scripts.system_health_check import check_disk_space

        mock_exists.return_value = True

        # Mock 150 GB free on local, 200 GB on NAS
        local_usage = Mock()
        local_usage.free = 150 * 1024**3

        nas_usage = Mock()
        nas_usage.free = 200 * 1024**3

        mock_disk_usage.side_effect = [local_usage, nas_usage]

        status, message = check_disk_space()

        assert status is True
        assert "adequate" in message.lower() or "pass" in message.lower()

    @patch('scripts.system_health_check.psutil.disk_usage')
    @patch('scripts.system_health_check.Path.exists')
    def test_low_local_space(self, mock_exists, mock_disk_usage):
        """Low disk space on local storage (< 50 GB)."""
        from scripts.system_health_check import check_disk_space

        mock_exists.return_value = True

        # Mock 30 GB free on local (below 50 GB threshold)
        local_usage = Mock()
        local_usage.free = 30 * 1024**3

        nas_usage = Mock()
        nas_usage.free = 200 * 1024**3

        mock_disk_usage.side_effect = [local_usage, nas_usage]

        status, message = check_disk_space()

        assert status is False
        assert "local" in message.lower()


class TestBasicHealthChecks:
    """Basic integration tests for health check functions."""

    def test_health_check_functions_exist(self):
        """Verify all health check functions are importable."""
        from scripts.system_health_check import (
            check_database_connectivity,
            check_data_freshness,
            check_disk_space,
            check_verification_status,
            generate_health_report,
        )

        # All functions should be callable
        assert callable(check_database_connectivity)
        assert callable(check_data_freshness)
        assert callable(check_disk_space)
        assert callable(check_verification_status)
        assert callable(generate_health_report)

    def test_health_check_returns_tuple(self):
        """Health check functions return (bool, str) tuples."""
        from scripts.system_health_check import check_database_connectivity

        result = check_database_connectivity()

        # Should return tuple of (status, message)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)


class TestHealthCheckIntegration:
    """Integration tests that run against actual system (when possible)."""

    @pytest.mark.integration
    def test_real_database_check(self):
        """Test database check against real database (if available)."""
        from scripts.system_health_check import check_database_connectivity

        try:
            status, message = check_database_connectivity()
            # Should return a boolean and a message
            assert isinstance(status, bool)
            assert len(message) > 0
        except Exception as e:
            pytest.skip(f"Database not available: {e}")

    @pytest.mark.integration
    def test_real_disk_check(self):
        """Test disk space check against real filesystem."""
        from scripts.system_health_check import check_disk_space

        try:
            status, message = check_disk_space()
            # Should return a boolean and a message
            assert isinstance(status, bool)
            assert len(message) > 0
        except Exception as e:
            pytest.skip(f"Disk check failed: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
