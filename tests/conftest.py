"""
Test fixtures and utilities for Claude Memory System tests
Provides reusable test data, fixtures, and helper functions
"""

import pytest
import os
import sys
import tempfile
from datetime import datetime, timedelta
from typing import List, Dict
from pathlib import Path

# Add backend directory to Python path so imports work from project root
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


# Test data fixtures

@pytest.fixture
def sample_messages_short() -> List[Dict]:
    """Short conversation for testing"""
    return [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there! How can I help you?"}
    ]


@pytest.fixture
def sample_messages_medium() -> List[Dict]:
    """Medium-length conversation for testing"""
    return [
        {"role": "user", "content": "I want to build a FastAPI service"},
        {"role": "assistant", "content": "Great! Let's start by setting up the project structure."},
        {"role": "user", "content": "What dependencies do I need?"},
        {"role": "assistant", "content": "You'll need fastapi, uvicorn, pydantic, and sqlalchemy."},
        {"role": "user", "content": "How do I structure the database?"},
        {"role": "assistant", "content": "Let's create models using SQLAlchemy ORM..."}
    ]


@pytest.fixture
def sample_messages_long() -> List[Dict]:
    """Long conversation for testing importance scoring"""
    messages = []
    for i in range(50):
        messages.append({
            "role": "user",
            "content": f"Question {i}: Can you explain this concept?"
        })
        messages.append({
            "role": "assistant",
            "content": f"Answer {i}: Here's a detailed explanation of the concept..."
        })
    return messages


@pytest.fixture
def sample_conversation_data() -> Dict:
    """Complete conversation data structure"""
    return {
        "platform": "claude_web",
        "timestamp": datetime.now().isoformat(),
        "messages": [
            {"role": "user", "content": "Build a memory system"},
            {"role": "assistant", "content": "Let's design the architecture..."}
        ],
        "working_dir": "/test/project",
        "project": "test-project"
    }


@pytest.fixture
def temp_db_path():
    """Create temporary database path for testing"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def temp_test_dir():
    """Create temporary directory for testing"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    import shutil
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


# Helper functions

def create_test_conversation(
    platform: str = "claude_web",
    content: str = "Test conversation",
    working_dir: str = None,
    importance: int = 5,
    timestamp: datetime = None
) -> Dict:
    """Create a test conversation data structure"""
    return {
        "platform": platform,
        "timestamp": (timestamp or datetime.now()).isoformat(),
        "messages": [
            {"role": "user", "content": content}
        ],
        "working_dir": working_dir,
        "importance": importance
    }


def create_multiple_conversations(count: int, **kwargs) -> List[Dict]:
    """Create multiple test conversations"""
    conversations = []
    for i in range(count):
        conv = create_test_conversation(
            content=f"Test conversation {i}",
            **kwargs
        )
        conversations.append(conv)
    return conversations


def assert_conversation_in_context(context: str, search_term: str):
    """Assert that a conversation appears in context"""
    assert search_term.lower() in context.lower(), \
        f"Expected '{search_term}' to be in context"


def assert_conversation_not_in_context(context: str, search_term: str):
    """Assert that a conversation does not appear in context"""
    assert search_term.lower() not in context.lower(), \
        f"Expected '{search_term}' to NOT be in context"


# Platform-specific fixtures

@pytest.fixture
def claude_web_conversation() -> Dict:
    """Sample Claude Web conversation"""
    return {
        "platform": "claude_web",
        "timestamp": datetime.now().isoformat(),
        "messages": [
            {"role": "user", "content": "Help me understand async programming"},
            {"role": "assistant", "content": "Async programming allows concurrent execution..."}
        ]
    }


@pytest.fixture
def claude_code_conversation() -> Dict:
    """Sample Claude Code conversation"""
    return {
        "platform": "claude_code",
        "timestamp": datetime.now().isoformat(),
        "messages": [
            {"role": "user", "content": "Refactor this function"},
            {"role": "assistant", "content": "I'll refactor it to be more efficient..."}
        ],
        "working_dir": "/home/user/project"
    }


@pytest.fixture
def antigravity_conversation() -> Dict:
    """Sample Antigravity conversation"""
    return {
        "platform": "antigravity",
        "timestamp": datetime.now().isoformat(),
        "messages": [
            {"role": "user", "content": "Design a system architecture"},
            {"role": "assistant", "content": "Let's create a microservices architecture..."}
        ]
    }


# Time-based fixtures

@pytest.fixture
def old_timestamp():
    """Timestamp from 48 hours ago"""
    return datetime.now() - timedelta(hours=48)


@pytest.fixture
def recent_timestamp():
    """Timestamp from 1 hour ago"""
    return datetime.now() - timedelta(hours=1)


@pytest.fixture
def current_timestamp():
    """Current timestamp"""
    return datetime.now()


# Database test utilities

class DatabaseTestHelper:
    """Helper class for database testing"""

    @staticmethod
    def count_conversations(db, **filters):
        """Count conversations matching filters"""
        conversations = db.get_recent_conversations(
            hours=24*365,  # Get all
            min_importance=0,
            **filters
        )
        return len(conversations)

    @staticmethod
    def get_conversation_by_content(db, content: str):
        """Find conversation by content substring"""
        conversations = db.get_recent_conversations(
            hours=24*365,
            min_importance=0
        )
        for conv in conversations:
            if content in conv["full_content"]:
                return conv
        return None

    @staticmethod
    def clear_all_conversations(db):
        """Clear all conversations from database"""
        db.conn.execute("DELETE FROM conversations")
        db.conn.commit()


# API test utilities

class APITestHelper:
    """Helper class for API testing"""

    @staticmethod
    def add_conversation(client, **kwargs):
        """Add conversation via API and return response"""
        default_data = {
            "platform": "claude_web",
            "timestamp": datetime.now().isoformat(),
            "messages": [{"role": "user", "content": "Test"}]
        }
        data = {**default_data, **kwargs}
        return client.post("/api/conversations", json=data)

    @staticmethod
    def get_context(client, **params):
        """Get context via API and return response"""
        default_params = {"hours": 24}
        query_params = {**default_params, **params}
        return client.get("/api/context", params=query_params)

    @staticmethod
    def assert_api_success(response):
        """Assert API response is successful"""
        assert response.status_code == 200
        return response.json()

    @staticmethod
    def assert_api_error(response, expected_code=422):
        """Assert API response is an error"""
        assert response.status_code == expected_code


# Mock data generators

def generate_realistic_conversation(topic: str = "programming") -> List[Dict]:
    """Generate realistic conversation based on topic"""
    topics = {
        "programming": [
            {"role": "user", "content": "How do I implement authentication in FastAPI?"},
            {"role": "assistant", "content": "I'll help you implement JWT authentication. First, install python-jose..."},
            {"role": "user", "content": "What about password hashing?"},
            {"role": "assistant", "content": "Use passlib with bcrypt for secure password hashing..."}
        ],
        "architecture": [
            {"role": "user", "content": "Design a microservices architecture"},
            {"role": "assistant", "content": "Let's design a scalable microservices system with API gateway..."},
            {"role": "user", "content": "How do services communicate?"},
            {"role": "assistant", "content": "Use REST APIs or message queues like RabbitMQ..."}
        ],
        "database": [
            {"role": "user", "content": "Design a database schema for users"},
            {"role": "assistant", "content": "Let's create a normalized schema with users, profiles, and permissions..."},
            {"role": "user", "content": "What about indexing?"},
            {"role": "assistant", "content": "Add indexes on frequently queried columns like email and username..."}
        ]
    }
    return topics.get(topic, topics["programming"])


# Performance testing utilities

class PerformanceTestHelper:
    """Helper class for performance testing"""

    @staticmethod
    def measure_time(func, *args, **kwargs):
        """Measure execution time of a function"""
        import time
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        return result, elapsed

    @staticmethod
    def assert_performance(elapsed: float, max_seconds: float, operation: str):
        """Assert operation completed within time limit"""
        assert elapsed < max_seconds, \
            f"{operation} took {elapsed:.2f}s, expected < {max_seconds}s"


# Pytest configuration

def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )
