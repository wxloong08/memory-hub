"""
Tests for Pydantic models
Tests model validation, serialization, and data integrity
"""

import pytest
from datetime import datetime
from pydantic import ValidationError
from backend.models import Conversation, Topic, Decision, Preference


class TestConversationModel:
    """Test Conversation model"""

    def test_conversation_minimal_fields(self):
        """Test creating conversation with minimal required fields"""
        conv = Conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content="Test conversation"
        )

        assert conv.platform == "claude_web"
        assert conv.full_content == "Test conversation"
        assert conv.importance == 5  # Default value
        assert conv.status == "completed"  # Default value

    def test_conversation_all_fields(self):
        """Test creating conversation with all fields"""
        now = datetime.now()
        conv = Conversation(
            id="test-id-123",
            platform="claude_code",
            timestamp=now,
            project="test-project",
            working_dir="/home/user/project",
            summary="Test summary",
            full_content="Full conversation content",
            importance=8,
            status="active"
        )

        assert conv.id == "test-id-123"
        assert conv.platform == "claude_code"
        assert conv.timestamp == now
        assert conv.project == "test-project"
        assert conv.working_dir == "/home/user/project"
        assert conv.summary == "Test summary"
        assert conv.importance == 8
        assert conv.status == "active"

    def test_conversation_missing_required_fields(self):
        """Test that missing required fields raise validation error"""
        with pytest.raises(ValidationError):
            Conversation(
                platform="claude_web"
                # Missing timestamp and full_content
            )

    def test_conversation_invalid_platform_type(self):
        """Test that invalid platform type raises error"""
        with pytest.raises(ValidationError):
            Conversation(
                platform=123,  # Should be string
                timestamp=datetime.now(),
                full_content="Test"
            )

    def test_conversation_invalid_timestamp_type(self):
        """Test that invalid timestamp type raises error"""
        with pytest.raises(ValidationError):
            Conversation(
                platform="claude_web",
                timestamp="not-a-datetime",
                full_content="Test"
            )

    def test_conversation_optional_fields_none(self):
        """Test that optional fields can be None"""
        conv = Conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content="Test",
            project=None,
            working_dir=None,
            summary=None
        )

        assert conv.project is None
        assert conv.working_dir is None
        assert conv.summary is None

    def test_conversation_serialization(self):
        """Test conversation serialization to dict"""
        conv = Conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content="Test",
            importance=7
        )

        data = conv.model_dump()
        assert isinstance(data, dict)
        assert data["platform"] == "claude_web"
        assert data["importance"] == 7

    def test_conversation_json_serialization(self):
        """Test conversation serialization to JSON"""
        conv = Conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content="Test"
        )

        json_str = conv.model_dump_json()
        assert isinstance(json_str, str)
        assert "claude_web" in json_str


class TestTopicModel:
    """Test Topic model"""

    def test_topic_creation(self):
        """Test creating topic"""
        topic = Topic(
            conversation_id="conv-123",
            topic="FastAPI development"
        )

        assert topic.conversation_id == "conv-123"
        assert topic.topic == "FastAPI development"

    def test_topic_missing_fields(self):
        """Test that missing required fields raise error"""
        with pytest.raises(ValidationError):
            Topic(conversation_id="conv-123")  # Missing topic

    def test_topic_invalid_types(self):
        """Test that invalid types raise error"""
        with pytest.raises(ValidationError):
            Topic(
                conversation_id=123,  # Should be string
                topic="Test"
            )


class TestDecisionModel:
    """Test Decision model"""

    def test_decision_creation(self):
        """Test creating decision"""
        now = datetime.now()
        decision = Decision(
            conversation_id="conv-123",
            decision="Use FastAPI for the backend",
            timestamp=now
        )

        assert decision.conversation_id == "conv-123"
        assert decision.decision == "Use FastAPI for the backend"
        assert decision.timestamp == now

    def test_decision_missing_fields(self):
        """Test that missing required fields raise error"""
        with pytest.raises(ValidationError):
            Decision(
                conversation_id="conv-123"
                # Missing decision and timestamp
            )

    def test_decision_serialization(self):
        """Test decision serialization"""
        decision = Decision(
            conversation_id="conv-123",
            decision="Use SQLite",
            timestamp=datetime.now()
        )

        data = decision.model_dump()
        assert data["decision"] == "Use SQLite"


class TestPreferenceModel:
    """Test Preference model"""

    def test_preference_creation(self):
        """Test creating preference"""
        now = datetime.now()
        pref = Preference(
            category="coding_style",
            key="indentation",
            value="4 spaces",
            confidence=0.9,
            last_updated=now
        )

        assert pref.category == "coding_style"
        assert pref.key == "indentation"
        assert pref.value == "4 spaces"
        assert pref.confidence == 0.9
        assert pref.last_updated == now

    def test_preference_default_confidence(self):
        """Test that confidence has default value"""
        pref = Preference(
            category="test",
            key="test",
            value="test",
            last_updated=datetime.now()
        )

        assert pref.confidence == 0.5  # Default value

    def test_preference_confidence_bounds(self):
        """Test preference with boundary confidence values"""
        # Minimum confidence
        pref_min = Preference(
            category="test",
            key="test",
            value="test",
            confidence=0.0,
            last_updated=datetime.now()
        )
        assert pref_min.confidence == 0.0

        # Maximum confidence
        pref_max = Preference(
            category="test",
            key="test",
            value="test",
            confidence=1.0,
            last_updated=datetime.now()
        )
        assert pref_max.confidence == 1.0

    def test_preference_missing_fields(self):
        """Test that missing required fields raise error"""
        with pytest.raises(ValidationError):
            Preference(
                category="test",
                key="test"
                # Missing value and last_updated
            )


class TestModelInteroperability:
    """Test models working together"""

    def test_conversation_with_topics(self):
        """Test creating conversation and related topics"""
        conv = Conversation(
            id="conv-123",
            platform="claude_web",
            timestamp=datetime.now(),
            full_content="Discussion about FastAPI and databases"
        )

        topic1 = Topic(conversation_id=conv.id, topic="FastAPI")
        topic2 = Topic(conversation_id=conv.id, topic="Databases")

        assert topic1.conversation_id == conv.id
        assert topic2.conversation_id == conv.id

    def test_conversation_with_decisions(self):
        """Test creating conversation and related decisions"""
        conv = Conversation(
            id="conv-456",
            platform="claude_code",
            timestamp=datetime.now(),
            full_content="Decided on architecture"
        )

        decision = Decision(
            conversation_id=conv.id,
            decision="Use microservices architecture",
            timestamp=datetime.now()
        )

        assert decision.conversation_id == conv.id


class TestModelValidation:
    """Test model validation rules"""

    def test_empty_string_validation(self):
        """Test handling of empty strings"""
        # Empty platform should be accepted (no validation yet)
        conv = Conversation(
            platform="",
            timestamp=datetime.now(),
            full_content="Test"
        )
        assert conv.platform == ""

    def test_very_long_content(self):
        """Test handling of very long content"""
        long_content = "A" * 100000  # 100KB

        conv = Conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content=long_content
        )

        assert len(conv.full_content) == 100000

    def test_special_characters_in_content(self):
        """Test handling of special characters"""
        special_content = "Test with 'quotes', \"double\", and unicode: 你好 🎉"

        conv = Conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content=special_content
        )

        assert conv.full_content == special_content

    def test_whitespace_handling(self):
        """Test handling of whitespace in fields"""
        conv = Conversation(
            platform="  claude_web  ",
            timestamp=datetime.now(),
            full_content="  Test content  "
        )

        # Pydantic doesn't strip by default
        assert conv.platform == "  claude_web  "


class TestModelDefaults:
    """Test model default values"""

    def test_conversation_defaults(self):
        """Test conversation default values"""
        conv = Conversation(
            platform="claude_web",
            timestamp=datetime.now(),
            full_content="Test"
        )

        assert conv.id is None
        assert conv.project is None
        assert conv.working_dir is None
        assert conv.summary is None
        assert conv.importance == 5
        assert conv.status == "completed"

    def test_preference_defaults(self):
        """Test preference default values"""
        pref = Preference(
            category="test",
            key="test",
            value="test",
            last_updated=datetime.now()
        )

        assert pref.confidence == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
