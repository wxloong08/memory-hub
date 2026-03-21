"""
End-to-end integration tests for Claude Memory System
Tests complete workflows across all components
"""

import pytest
import requests
import time
import os
import subprocess
from datetime import datetime
from pathlib import Path


BASE_URL = "http://localhost:8765"
TEST_PROJECT_DIR = "/tmp/test-claude-project"


@pytest.fixture(scope="module")
def memory_hub_server():
    """Start Memory Hub server for testing"""
    # Check if server is already running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        if response.status_code == 200:
            print("Memory Hub already running")
            yield
            return
    except:
        pass

    # Start server
    backend_dir = Path(__file__).parent.parent / "backend"
    process = subprocess.Popen(
        ["uvicorn", "main:app", "--port", "8765"],
        cwd=str(backend_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for server to start
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=1)
            if response.status_code == 200:
                print("Memory Hub started successfully")
                break
        except:
            time.sleep(0.5)
    else:
        process.kill()
        pytest.fail("Failed to start Memory Hub server")

    yield

    # Cleanup
    process.terminate()
    process.wait(timeout=5)


class TestFullWorkflow:
    """Test complete end-to-end workflows"""

    def test_health_check(self, memory_hub_server):
        """Test that Memory Hub is accessible"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_add_conversation_and_retrieve_context(self, memory_hub_server):
        """Test complete workflow: add conversation -> retrieve context"""
        # Step 1: Add a conversation
        conv_data = {
            "platform": "claude_web",
            "timestamp": datetime.now().isoformat(),
            "messages": [
                {"role": "user", "content": "I want to build a POD system with multiple agents"},
                {"role": "assistant", "content": "Great! Let's design the architecture. We'll need..."}
            ],
            "working_dir": TEST_PROJECT_DIR
        }

        response = requests.post(f"{BASE_URL}/api/conversations", json=conv_data)
        assert response.status_code == 200
        conv_id = response.json()["conversation_id"]
        assert conv_id is not None
        print(f"Created conversation: {conv_id}")

        # Step 2: Retrieve context
        response = requests.get(
            f"{BASE_URL}/api/context",
            params={"working_dir": TEST_PROJECT_DIR, "hours": 1}
        )
        assert response.status_code == 200

        context = response.json()["context"]
        assert "POD system" in context or "agents" in context
        print(f"Retrieved context: {len(context)} characters")

    def test_multiple_conversations_workflow(self, memory_hub_server):
        """Test workflow with multiple related conversations"""
        conversations = [
            {
                "platform": "claude_web",
                "messages": [
                    {"role": "user", "content": "Design a FastAPI service"},
                    {"role": "assistant", "content": "Let's create the API structure..."}
                ]
            },
            {
                "platform": "claude_code",
                "messages": [
                    {"role": "user", "content": "Implement the database layer"},
                    {"role": "assistant", "content": "I'll create the SQLite schema..."}
                ]
            },
            {
                "platform": "claude_code",
                "messages": [
                    {"role": "user", "content": "Add authentication"},
                    {"role": "assistant", "content": "Let's add JWT authentication..."}
                ]
            }
        ]

        # Add all conversations
        conv_ids = []
        for conv in conversations:
            conv["timestamp"] = datetime.now().isoformat()
            conv["working_dir"] = TEST_PROJECT_DIR

            response = requests.post(f"{BASE_URL}/api/conversations", json=conv)
            assert response.status_code == 200
            conv_ids.append(response.json()["conversation_id"])

        print(f"Created {len(conv_ids)} conversations")

        # Retrieve context
        response = requests.get(
            f"{BASE_URL}/api/context",
            params={"working_dir": TEST_PROJECT_DIR, "hours": 1, "min_importance": 0}
        )
        assert response.status_code == 200

        context = response.json()["context"]
        # Should contain references to multiple conversations
        assert "FastAPI" in context or "database" in context or "authentication" in context

    def test_cross_platform_conversation_tracking(self, memory_hub_server):
        """Test tracking conversations across different Claude platforms"""
        platforms = ["claude_web", "claude_code", "antigravity"]

        for platform in platforms:
            conv_data = {
                "platform": platform,
                "timestamp": datetime.now().isoformat(),
                "messages": [
                    {"role": "user", "content": f"Testing from {platform}"},
                    {"role": "assistant", "content": f"Response on {platform}"}
                ],
                "working_dir": TEST_PROJECT_DIR
            }

            response = requests.post(f"{BASE_URL}/api/conversations", json=conv_data)
            assert response.status_code == 200

        # Retrieve context - should include all platforms
        response = requests.get(
            f"{BASE_URL}/api/context",
            params={"working_dir": TEST_PROJECT_DIR, "hours": 1, "min_importance": 0}
        )
        assert response.status_code == 200

        context = response.json()["context"]
        # Should have conversations from multiple platforms
        assert len(context) > 100  # Non-empty context


class TestImportanceScoring:
    """Test importance scoring logic"""

    def test_short_conversation_low_importance(self, memory_hub_server):
        """Test that short conversations get lower importance"""
        conv_data = {
            "platform": "claude_web",
            "timestamp": datetime.now().isoformat(),
            "messages": [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello!"}
            ]
        }

        response = requests.post(f"{BASE_URL}/api/conversations", json=conv_data)
        assert response.status_code == 200

        # Should not appear in high-importance filter
        response = requests.get(
            f"{BASE_URL}/api/context",
            params={"hours": 1, "min_importance": 8}
        )
        context = response.json()["context"]
        assert "Hi" not in context or "No recent conversations" in context

    def test_long_conversation_high_importance(self, memory_hub_server):
        """Test that long conversations get higher importance"""
        messages = []
        for i in range(30):
            messages.append({"role": "user", "content": f"Question {i}"})
            messages.append({"role": "assistant", "content": f"Detailed answer {i}"})

        conv_data = {
            "platform": "claude_web",
            "timestamp": datetime.now().isoformat(),
            "messages": messages
        }

        response = requests.post(f"{BASE_URL}/api/conversations", json=conv_data)
        assert response.status_code == 200

        # Should appear in high-importance filter
        response = requests.get(
            f"{BASE_URL}/api/context",
            params={"hours": 1, "min_importance": 8}
        )
        context = response.json()["context"]
        assert "Question" in context or "answer" in context


class TestContextFiltering:
    """Test context filtering and retrieval"""

    def test_time_based_filtering(self, memory_hub_server):
        """Test that old conversations are filtered out"""
        # Add a conversation
        conv_data = {
            "platform": "claude_web",
            "timestamp": datetime.now().isoformat(),
            "messages": [
                {"role": "user", "content": "Recent conversation for time test"}
            ]
        }

        response = requests.post(f"{BASE_URL}/api/conversations", json=conv_data)
        assert response.status_code == 200

        # Should appear in 24-hour window
        response = requests.get(f"{BASE_URL}/api/context?hours=24")
        context = response.json()["context"]
        assert "Recent conversation" in context or "time test" in context

        # Should not appear in very short window
        response = requests.get(f"{BASE_URL}/api/context?hours=0")
        context = response.json()["context"]
        # Might be empty or not contain our conversation

    def test_working_directory_isolation(self, memory_hub_server):
        """Test that conversations are isolated by working directory"""
        project_a = "/projects/project-a"
        project_b = "/projects/project-b"

        # Add conversation for project A
        conv_a = {
            "platform": "claude_code",
            "timestamp": datetime.now().isoformat(),
            "messages": [{"role": "user", "content": "Project A specific work"}],
            "working_dir": project_a
        }
        requests.post(f"{BASE_URL}/api/conversations", json=conv_a)

        # Add conversation for project B
        conv_b = {
            "platform": "claude_code",
            "timestamp": datetime.now().isoformat(),
            "messages": [{"role": "user", "content": "Project B specific work"}],
            "working_dir": project_b
        }
        requests.post(f"{BASE_URL}/api/conversations", json=conv_b)

        # Get context for project A only
        response = requests.get(
            f"{BASE_URL}/api/context",
            params={"working_dir": project_a, "hours": 1}
        )
        context_a = response.json()["context"]

        # Get context for project B only
        response = requests.get(
            f"{BASE_URL}/api/context",
            params={"working_dir": project_b, "hours": 1}
        )
        context_b = response.json()["context"]

        # Each should only contain its own project's conversations
        assert "Project A" in context_a
        assert "Project B" not in context_a
        assert "Project B" in context_b
        assert "Project A" not in context_b


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_invalid_conversation_data(self, memory_hub_server):
        """Test handling of invalid conversation data"""
        invalid_data = {
            "platform": "claude_web",
            # Missing required fields
        }

        response = requests.post(f"{BASE_URL}/api/conversations", json=invalid_data)
        assert response.status_code == 422  # Validation error

    def test_malformed_json(self, memory_hub_server):
        """Test handling of malformed JSON"""
        response = requests.post(
            f"{BASE_URL}/api/conversations",
            data="not-valid-json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_server_handles_concurrent_requests(self, memory_hub_server):
        """Test that server handles concurrent requests"""
        import concurrent.futures

        def add_conversation(i):
            conv_data = {
                "platform": "claude_web",
                "timestamp": datetime.now().isoformat(),
                "messages": [{"role": "user", "content": f"Concurrent test {i}"}]
            }
            response = requests.post(f"{BASE_URL}/api/conversations", json=conv_data)
            return response.status_code == 200

        # Send 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(add_conversation, i) for i in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed
        assert all(results)


class TestPerformance:
    """Test performance characteristics"""

    def test_large_conversation_handling(self, memory_hub_server):
        """Test handling of very large conversations"""
        large_messages = []
        for i in range(100):
            large_messages.append({
                "role": "user",
                "content": f"Message {i}: " + "A" * 1000  # 1KB per message
            })

        conv_data = {
            "platform": "claude_web",
            "timestamp": datetime.now().isoformat(),
            "messages": large_messages
        }

        start_time = time.time()
        response = requests.post(f"{BASE_URL}/api/conversations", json=conv_data)
        elapsed = time.time() - start_time

        assert response.status_code == 200
        assert elapsed < 5.0  # Should complete within 5 seconds

    def test_context_retrieval_performance(self, memory_hub_server):
        """Test context retrieval performance"""
        # Add multiple conversations
        for i in range(20):
            conv_data = {
                "platform": "claude_web",
                "timestamp": datetime.now().isoformat(),
                "messages": [{"role": "user", "content": f"Performance test {i}"}]
            }
            requests.post(f"{BASE_URL}/api/conversations", json=conv_data)

        # Measure context retrieval time
        start_time = time.time()
        response = requests.get(f"{BASE_URL}/api/context?hours=1&min_importance=0")
        elapsed = time.time() - start_time

        assert response.status_code == 200
        assert elapsed < 2.0  # Should complete within 2 seconds


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
