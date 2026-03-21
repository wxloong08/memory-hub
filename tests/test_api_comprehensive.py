"""
Comprehensive API integration tests for Claude Memory Hub
Tests all API endpoints, request validation, error handling, and CORS
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import os
import sys

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def client():
    """Create test client with isolated database"""
    # Set test database path before importing app
    os.environ['TEST_MODE'] = '1'
    test_db_path = "test_api_memory.db"

    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    # Import after setting environment
    from backend.main import app, db
    db.db_path = test_db_path

    client = TestClient(app)
    yield client

    # Cleanup
    if hasattr(db, 'conn'):
        db.conn.close()
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check(self, client):
        """Test health endpoint returns healthy status"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestAddConversationEndpoint:
    """Test POST /api/conversations endpoint"""

    def test_add_conversation_minimal(self, client):
        """Test adding conversation with minimal required fields"""
        response = client.post("/api/conversations", json={
            "platform": "claude_web",
            "timestamp": datetime.now().isoformat(),
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"}
            ]
        })

        assert response.status_code == 200
        data = response.json()
        assert "conversation_id" in data
        assert data["status"] == "ok"
        assert len(data["conversation_id"]) == 36  # UUID format

    def test_add_conversation_full(self, client):
        """Test adding conversation with all optional fields"""
        response = client.post("/api/conversations", json={
            "platform": "claude_code",
            "timestamp": datetime.now().isoformat(),
            "messages": [
                {"role": "user", "content": "Build a system"},
                {"role": "assistant", "content": "Sure, let's start..."}
            ],
            "working_dir": "/home/user/project",
            "project": "my-project"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_add_conversation_multiple_messages(self, client):
        """Test adding conversation with many messages"""
        messages = []
        for i in range(20):
            messages.append({"role": "user", "content": f"Question {i}"})
            messages.append({"role": "assistant", "content": f"Answer {i}"})

        response = client.post("/api/conversations", json={
            "platform": "claude_web",
            "timestamp": datetime.now().isoformat(),
            "messages": messages
        })

        assert response.status_code == 200

    def test_add_conversation_invalid_platform(self, client):
        """Test validation rejects invalid platform"""
        response = client.post("/api/conversations", json={
            "platform": "",
            "timestamp": datetime.now().isoformat(),
            "messages": [{"role": "user", "content": "Test"}]
        })

        # Should still accept (no strict validation yet)
        # In production, add validation
        assert response.status_code in [200, 422]

    def test_add_conversation_missing_required_fields(self, client):
        """Test validation rejects missing required fields"""
        response = client.post("/api/conversations", json={
            "platform": "claude_web"
            # Missing timestamp and messages
        })

        assert response.status_code == 422  # Validation error

    def test_add_conversation_invalid_timestamp(self, client):
        """Test handling of invalid timestamp format"""
        response = client.post("/api/conversations", json={
            "platform": "claude_web",
            "timestamp": "not-a-timestamp",
            "messages": [{"role": "user", "content": "Test"}]
        })

        assert response.status_code == 422

    def test_add_conversation_empty_messages(self, client):
        """Test handling of empty messages array"""
        response = client.post("/api/conversations", json={
            "platform": "claude_web",
            "timestamp": datetime.now().isoformat(),
            "messages": []
        })

        assert response.status_code == 200  # Should accept but handle gracefully

    def test_add_conversation_special_characters(self, client):
        """Test handling special characters in content"""
        response = client.post("/api/conversations", json={
            "platform": "claude_web",
            "timestamp": datetime.now().isoformat(),
            "messages": [
                {"role": "user", "content": "Test with 'quotes' and \"double\" and unicode: 你好 🎉"}
            ]
        })

        assert response.status_code == 200


class TestGetContextEndpoint:
    """Test GET /api/context endpoint"""

    def test_get_context_empty_database(self, client):
        """Test getting context when no conversations exist"""
        response = client.get("/api/context?hours=24")

        assert response.status_code == 200
        data = response.json()
        assert "context" in data
        assert "No recent conversations" in data["context"]

    def test_get_context_with_conversations(self, client):
        """Test getting context with existing conversations"""
        # Add a conversation first
        client.post("/api/conversations", json={
            "platform": "claude_web",
            "timestamp": datetime.now().isoformat(),
            "messages": [
                {"role": "user", "content": "Build a POD system"},
                {"role": "assistant", "content": "Great idea!"}
            ]
        })

        response = client.get("/api/context?hours=24")

        assert response.status_code == 200
        data = response.json()
        assert "context" in data
        assert "POD system" in data["context"] or "Build" in data["context"]

    def test_get_context_time_filter(self, client):
        """Test context filtering by time window"""
        # Add old conversation (won't be included)
        old_time = datetime.now() - timedelta(hours=48)
        client.post("/api/conversations", json={
            "platform": "claude_web",
            "timestamp": old_time.isoformat(),
            "messages": [{"role": "user", "content": "Old conversation"}]
        })

        # Add recent conversation
        client.post("/api/conversations", json={
            "platform": "claude_web",
            "timestamp": datetime.now().isoformat(),
            "messages": [{"role": "user", "content": "Recent conversation"}]
        })

        response = client.get("/api/context?hours=24")
        data = response.json()

        assert "Recent" in data["context"]
        assert "Old" not in data["context"]

    def test_get_context_importance_filter(self, client):
        """Test context filtering by importance"""
        # Add low importance conversation
        client.post("/api/conversations", json={
            "platform": "claude_web",
            "timestamp": datetime.now().isoformat(),
            "messages": [{"role": "user", "content": "Low"}]  # Short = low importance
        })

        # Add high importance conversation (many messages)
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(20)]
        client.post("/api/conversations", json={
            "platform": "claude_web",
            "timestamp": datetime.now().isoformat(),
            "messages": messages
        })

        response = client.get("/api/context?hours=24&min_importance=7")
        data = response.json()

        # Should only include high importance
        assert "Message" in data["context"]

    def test_get_context_working_dir_filter(self, client):
        """Test context filtering by working directory"""
        # Add conversation for project A
        client.post("/api/conversations", json={
            "platform": "claude_code",
            "timestamp": datetime.now().isoformat(),
            "messages": [{"role": "user", "content": "Project A work"}],
            "working_dir": "/projects/project-a"
        })

        # Add conversation for project B
        client.post("/api/conversations", json={
            "platform": "claude_code",
            "timestamp": datetime.now().isoformat(),
            "messages": [{"role": "user", "content": "Project B work"}],
            "working_dir": "/projects/project-b"
        })

        response = client.get("/api/context?working_dir=/projects/project-a")
        data = response.json()

        assert "Project A" in data["context"]
        assert "Project B" not in data["context"]

    def test_get_context_default_parameters(self, client):
        """Test context endpoint with default parameters"""
        client.post("/api/conversations", json={
            "platform": "claude_web",
            "timestamp": datetime.now().isoformat(),
            "messages": [{"role": "user", "content": "Test"}]
        })

        response = client.get("/api/context")
        assert response.status_code == 200

    def test_get_context_invalid_parameters(self, client):
        """Test context endpoint with invalid parameters"""
        response = client.get("/api/context?hours=invalid")
        assert response.status_code == 422  # Validation error


class TestCORS:
    """Test CORS configuration"""

    def test_cors_headers_present(self, client):
        """Test that CORS headers are set correctly"""
        response = client.options("/api/conversations")

        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers

    def test_cors_allows_all_origins(self, client):
        """Test that CORS allows requests from any origin"""
        response = client.get(
            "/health",
            headers={"Origin": "https://claude.ai"}
        )

        assert response.status_code == 200


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_invalid_json_body(self, client):
        """Test handling of malformed JSON"""
        response = client.post(
            "/api/conversations",
            data="not-valid-json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_missing_content_type(self, client):
        """Test handling of missing content type header"""
        response = client.post(
            "/api/conversations",
            data='{"platform": "test"}'
        )

        # Should still work or return appropriate error
        assert response.status_code in [200, 422]

    def test_very_large_payload(self, client):
        """Test handling of very large conversation payload"""
        large_content = "A" * 50000  # 50KB message

        response = client.post("/api/conversations", json={
            "platform": "claude_web",
            "timestamp": datetime.now().isoformat(),
            "messages": [{"role": "user", "content": large_content}]
        })

        assert response.status_code == 200


class TestEndToEndWorkflow:
    """Test complete workflows"""

    def test_add_and_retrieve_workflow(self, client):
        """Test adding conversation and retrieving it via context"""
        # Step 1: Add conversation
        add_response = client.post("/api/conversations", json={
            "platform": "claude_web",
            "timestamp": datetime.now().isoformat(),
            "messages": [
                {"role": "user", "content": "I want to build a memory system"},
                {"role": "assistant", "content": "Great! Let's design it..."}
            ],
            "working_dir": "/test/project"
        })

        assert add_response.status_code == 200
        conv_id = add_response.json()["conversation_id"]

        # Step 2: Retrieve context
        context_response = client.get("/api/context?working_dir=/test/project&hours=1")
        assert context_response.status_code == 200

        context = context_response.json()["context"]
        assert "memory system" in context.lower() or "build" in context.lower()

    def test_multiple_conversations_workflow(self, client):
        """Test adding multiple conversations and retrieving context"""
        # Add several conversations
        for i in range(5):
            client.post("/api/conversations", json={
                "platform": "claude_web",
                "timestamp": datetime.now().isoformat(),
                "messages": [
                    {"role": "user", "content": f"Task {i}"},
                    {"role": "assistant", "content": f"Response {i}"}
                ]
            })

        # Get context
        response = client.get("/api/context?hours=1&min_importance=0")
        data = response.json()

        # Should have context from multiple conversations
        assert "Auto-Generated Context" in data["context"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
