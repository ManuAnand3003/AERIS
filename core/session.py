from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Message:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    model_used: Optional[str] = None
    query_type: Optional[str] = None


@dataclass
class Session:
    session_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))
    mode: str = "personal"
    messages: list[Message] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    idle_since: Optional[datetime] = None

    def add_message(self, role: str, content: str, **kwargs) -> Message:
        msg = Message(role=role, content=content, **kwargs)
        self.messages.append(msg)
        return msg

    def get_recent(self, n: int = 10) -> list[Message]:
        return self.messages[-n:]

    def mark_idle(self):
        self.idle_since = datetime.now()

    def mark_active(self):
        self.idle_since = None

    @property
    def is_idle(self) -> bool:
        if self.idle_since is None:
            return False
        return (datetime.now() - self.idle_since).seconds > 300