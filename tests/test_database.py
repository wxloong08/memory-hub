import pytest
from backend.database import Database
import os

def test_database_creates_tables():
    """Test that database initializes with correct schema"""
    db_path = "test_memory.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    db = Database(db_path)

    # Check tables exist
    tables = db.get_tables()
    assert "conversations" in tables
    assert "topics" in tables
    assert "decisions" in tables
    assert "preferences" in tables

    # Close connection before removing
    db.conn.close()
    os.remove(db_path)

def test_add_and_retrieve_conversation():
    """Test adding and retrieving conversations"""
    db_path = "test_memory.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    db = Database(db_path)
    
    from datetime import datetime
    
    # Add a conversation
    conv_id = db.add_conversation(
        platform="claude_web",
        timestamp=datetime.now(),
        full_content="User: Hello\nAssistant: Hi there!",
        summary="Greeting conversation",
        importance=7
    )
    
    assert conv_id is not None
    
    # Retrieve recent conversations
    conversations = db.get_recent_conversations(hours=1, min_importance=5)
    assert len(conversations) == 1
    assert conversations[0]["platform"] == "claude_web"
    assert conversations[0]["importance"] == 7
    
    # Close connection before removing
    db.conn.close()
    os.remove(db_path)
