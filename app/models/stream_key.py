"""
StreamKey model untuk mengelola multiple stream keys.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from app.database import Base


class StreamKey(Base):
    """Model untuk stream key YouTube"""
    __tablename__ = "stream_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # "Lofi 1", "Lofi 2", etc.
    stream_key = Column(String, unique=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'stream_key': self._mask_key(),
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def _mask_key(self) -> str:
        """Mask stream key untuk security (show only last 4 chars)"""
        if not self.stream_key:
            return ""
        if len(self.stream_key) <= 4:
            return self.stream_key
        return "****-****-" + self.stream_key[-4:]
    
    def get_full_key(self) -> str:
        """Get full stream key (untuk internal use only)"""
        return self.stream_key
    
    def __repr__(self):
        return f"<StreamKey(id={self.id}, name='{self.name}', active={self.is_active})>"
