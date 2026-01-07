from sqlalchemy import Column, Integer, String, DateTime, JSON
from app.database import Base
from datetime import datetime

class Playlist(Base):
    """
    Model untuk mengelola playlist video streaming.
    
    Attributes:
        id: Primary key
        name: Nama playlist
        mode: Mode pemutaran ('random' atau 'sequence')
        video_ids: List ID video dalam format JSON array
        created_at: Timestamp pembuatan playlist
    """
    __tablename__ = "playlists"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    mode = Column(String, default="sequence", nullable=False)  # 'random' atau 'sequence'
    video_ids = Column(JSON, default=list, nullable=False)  # List of video IDs
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<Playlist(id={self.id}, name='{self.name}', mode='{self.mode}')>"
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "mode": self.mode,
            "video_ids": self.video_ids,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
