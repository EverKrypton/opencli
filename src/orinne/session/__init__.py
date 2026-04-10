"""Session management for ORINNE."""

import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Message:
    role: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    tool_calls: List[Dict] = field(default_factory=list)
    tool_results: List[Dict] = field(default_factory=list)
    
    def to_api_format(self) -> Dict[str, Any]:
        msg = {"role": self.role, "content": self.content}
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        return msg
    
    @classmethod
    def from_api_format(cls, data: Dict) -> "Message":
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            tool_calls=data.get("tool_calls", []),
        )


@dataclass
class Session:
    id: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    messages: List[Message] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    total_tokens: int = 0
    total_cost: float = 0.0
    
    def add_message(self, role: str, content: str, **kwargs):
        self.messages.append(Message(role=role, content=content, **kwargs))
        self.updated_at = datetime.now().isoformat()
    
    def add_tool_result(self, tool_call_id: str, result: str):
        self.messages.append(Message(
            role="tool",
            content=result,
            tool_results=[{"tool_call_id": tool_call_id, "content": result}]
        ))
    
    def clear(self):
        self.messages = []
        self.total_tokens = 0
        self.total_cost = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Session":
        messages = [Message(**m) for m in data.get("messages", [])]
        return cls(
            id=data.get("id", "default"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            messages=messages,
            metadata=data.get("metadata", {}),
            total_tokens=data.get("total_tokens", 0),
            total_cost=data.get("total_cost", 0.0),
        )


class SessionManager:
    def __init__(self, session_dir: str = None):
        if session_dir:
            self.session_dir = Path(session_dir)
        elif os.environ.get("TERMUX_VERSION"):
            self.session_dir = Path.home() / ".orinne" / "sessions"
        else:
            self.session_dir = Path.home() / ".local" / "share" / "orinne" / "sessions"
        
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.current_session: Optional[Session] = None
    
    def create_session(self, session_id: str = None) -> Session:
        import uuid
        sid = session_id or str(uuid.uuid4())[:8]
        self.current_session = Session(id=sid)
        return self.current_session
    
    def load_session(self, session_id: str) -> Optional[Session]:
        path = self.session_dir / f"{session_id}.json"
        if path.exists():
            with open(path, "r") as f:
                data = json.load(f)
            self.current_session = Session.from_dict(data)
            return self.current_session
        return None
    
    def save_session(self):
        if self.current_session:
            path = self.session_dir / f"{self.current_session.id}.json"
            with open(path, "w") as f:
                json.dump(self.current_session.to_dict(), f, indent=2)
    
    def list_sessions(self) -> List[Dict]:
        sessions = []
        for path in self.session_dir.glob("*.json"):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                sessions.append({
                    "id": data.get("id"),
                    "created_at": data.get("created_at"),
                    "message_count": len(data.get("messages", [])),
                })
            except:
                continue
        
        sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return sessions
    
    def delete_session(self, session_id: str):
        path = self.session_dir / f"{session_id}.json"
        if path.exists():
            path.unlink()
    
    def get_or_create(self) -> Session:
        if self.current_session:
            return self.current_session
        return self.create_session()
