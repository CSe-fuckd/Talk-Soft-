from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List
import json

@dataclass
class ChatMessage:
    content: str
    sender: str
    emotion: str = "normal"
    alert: bool = False
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
        # 保证一定带时区
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)

    def to_dict(self):
        return {
            "content": self.content,
            "sender": self.sender,
            "emotion": self.emotion,
            "alert": self.alert,
            "timestamp": self.timestamp.isoformat()
        }

@dataclass
class ChatSession:
    session_start: datetime
    session_end: Optional[datetime] = None
    messages: List[ChatMessage] = field(default_factory=list)
    relationship_score: int = 50   # 新增关系分

    def to_dict(self):
        return {
            "session_start": self.session_start.isoformat(),
            "session_end": self.session_end.isoformat() if self.session_end else None,
            "messages": [m.to_dict() for m in self.messages],
            "relationship_score": self.relationship_score
        }


def parse_datetime(dt_str: str):
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def load_sessions_from_json(path: str = "logs.json") -> List[ChatSession]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []

    sessions = []
    for s_data in data:
        start = parse_datetime(s_data["session_start"])
        end = parse_datetime(s_data["session_end"]) if s_data["session_end"] else None
        msg_list = []
        for m_data in s_data["messages"]:
            msg = ChatMessage(
                content=m_data["content"],
                sender=m_data["sender"],
                emotion=m_data.get("emotion", "normal"),
                alert=m_data.get("alert", False),
                timestamp=parse_datetime(m_data["timestamp"])
            )
            msg_list.append(msg)
        rel_score = s_data.get("relationship_score", 50)
        session = ChatSession(
            session_start=start,
            session_end=end,
            messages=msg_list,
            relationship_score=rel_score
        )
        sessions.append(session)
    return sessions


def save_sessions_to_json(sessions: List[ChatSession], path: str = "logs.json"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump([s.to_dict() for s in sessions], f, indent=2)
