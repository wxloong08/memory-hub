from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class Conversation(BaseModel):
    id: Optional[str] = None
    platform: str  # 'claude_web', 'claude_code', 'antigravity'
    timestamp: datetime
    project: Optional[str] = None
    working_dir: Optional[str] = None
    summary: Optional[str] = None
    full_content: str
    importance: int = 5
    status: str = "completed"

class Topic(BaseModel):
    conversation_id: str
    topic: str

class Decision(BaseModel):
    conversation_id: str
    decision: str
    timestamp: datetime

class Preference(BaseModel):
    category: str
    key: str
    value: str
    confidence: float = 0.5
    last_updated: datetime
