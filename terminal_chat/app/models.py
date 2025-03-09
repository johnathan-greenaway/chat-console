from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime

@dataclass
class Message:
    """Represents a chat message"""
    id: int = None
    conversation_id: int = None
    role: str = ""  # 'user', 'assistant', 'system'
    content: str = ""
    timestamp: str = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        return cls(
            id=data.get('id'),
            conversation_id=data.get('conversation_id'),
            role=data.get('role', ''),
            content=data.get('content', ''),
            timestamp=data.get('timestamp')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp or datetime.now().isoformat()
        }

@dataclass
class Conversation:
    """Represents a chat conversation"""
    id: int = None
    title: str = ""
    model: str = ""
    created_at: str = None
    updated_at: str = None
    style: str = "default"
    tags: List[str] = None
    messages: List[Message] = None
    message_count: int = 0
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.messages is None:
            self.messages = []
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Conversation':
        messages = []
        if 'messages' in data:
            messages = [Message.from_dict(m) if isinstance(m, dict) else m 
                        for m in data.get('messages', [])]
            
        return cls(
            id=data.get('id'),
            title=data.get('title', ''),
            model=data.get('model', ''),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            style=data.get('style', 'default'),
            tags=data.get('tags', []),
            messages=messages,
            message_count=data.get('message_count', len(messages))
        )
    
    def to_dict(self) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        return {
            'id': self.id,
            'title': self.title,
            'model': self.model,
            'created_at': self.created_at or now,
            'updated_at': self.updated_at or now,
            'style': self.style,
            'tags': self.tags,
            'messages': [m.to_dict() if isinstance(m, Message) else m for m in self.messages],
            'message_count': self.message_count or len(self.messages)
        }
