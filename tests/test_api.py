import pytest
from fastapi.testclient import TestClient
from backend.main import app
from datetime import datetime
import os

client = TestClient(app)

def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_add_conversation_endpoint():
    """Test adding a conversation via API"""
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

def test_get_context_endpoint():
    """Test getting context summary"""
    response = client.get("/api/context?hours=24")

    assert response.status_code == 200
    data = response.json()
    assert "context" in data

def test_add_conversation_with_working_dir():
    """Test adding conversation with working directory"""
    response = client.post("/api/conversations", json={
        "platform": "claude_code",
        "timestamp": datetime.now().isoformat(),
        "messages": [
            {"role": "user", "content": "Build a FastAPI service"},
            {"role": "assistant", "content": "Let's create the service..."}
        ],
        "working_dir": "/test/project",
        "project": "test-project"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    
    # Verify we can retrieve it with working_dir filter (use min_importance=5 to include it)
    response = client.get("/api/context?working_dir=/test/project&hours=1&min_importance=5")
    assert response.status_code == 200
    context = response.json()["context"]
    assert "FastAPI" in context or "service" in context
