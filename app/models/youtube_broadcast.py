"""
Model untuk YouTube Broadcast.
Menyimpan info broadcast yang dibuat via YouTube API.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class YouTubeBroadcast(Base):
    """Model untuk YouTube broadcast"""
    __tablename__ = "youtube_broadcasts"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # YouTube IDs
    broadcast_id = Column(String, unique=True, nullable=False, index=True)
    stream_id = Column(String, unique=True, nullable=False)
    
    # Stream info
    stream_key = Column(String, nullable=False)
    rtmp_url = Column(String, nullable=False)
    ingestion_address = Column(String, nullable=False)
    
    # Broadcast info
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    broadcast_url = Column(String, nullable=False)
    
    # Settings
    privacy_status = Column(String, default='public')  # public, unlisted, private
    resolution = Column(String, default='1080p')
    frame_rate = Column(String, default='30fps')
    
    # Advanced settings
    latency_mode = Column(String, default='normal')  # normal, low, ultraLow
    enable_dvr = Column(Boolean, default=True)
    made_for_kids = Column(Boolean, default=False)
    category_id = Column(String, default='24')  # Default: Entertainment
    thumbnail_url = Column(String, nullable=True)
    enable_embed = Column(Boolean, default=True)
    enable_chat = Column(Boolean, default=True)
    
    # Discovery & License
    tags = Column(String, nullable=True)  # Comma separated
    language = Column(String, default='id')  # Default: Indonesian
    license = Column(String, default='youtube')  # youtube, creativeCommon
    
    # Auto Control
    auto_start = Column(Boolean, default=True)
    auto_stop = Column(Boolean, default=True)
    
    # Status
    status = Column(String, default='ready')  # ready, live, complete, error
    
    # Timestamps
    scheduled_start_time = Column(DateTime, nullable=True)
    actual_start_time = Column(DateTime, nullable=True)
    actual_end_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships (optional)
    live_history_id = Column(Integer, ForeignKey('live_history.id'), nullable=True)
    # live_history = relationship("LiveHistory", backref="youtube_broadcast")
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'broadcast_id': self.broadcast_id,
            'stream_id': self.stream_id,
            'stream_key': self._mask_stream_key(),
            'rtmp_url': self.rtmp_url,
            'title': self.title,
            'description': self.description,
            'broadcast_url': self.broadcast_url,
            'privacy_status': self.privacy_status,
            'resolution': self.resolution,
            'frame_rate': self.frame_rate,
            'status': self.status,
            'latency_mode': self.latency_mode,
            'enable_dvr': self.enable_dvr,
            'made_for_kids': self.made_for_kids,
            'category_id': self.category_id,
            'thumbnail_url': self.thumbnail_url,
            'enable_embed': self.enable_embed,
            'enable_chat': self.enable_chat,
            'tags': self.tags,
            'language': self.language,
            'license': self.license,
            'auto_start': self.auto_start,
            'auto_stop': self.auto_stop,
            'scheduled_start_time': self.scheduled_start_time.isoformat() if self.scheduled_start_time else None,
            'actual_start_time': self.actual_start_time.isoformat() if self.actual_start_time else None,
            'actual_end_time': self.actual_end_time.isoformat() if self.actual_end_time else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def _mask_stream_key(self) -> str:
        """Mask stream key untuk security (show only last 4 chars)"""
        if not self.stream_key:
            return ""
        if len(self.stream_key) <= 4:
            return self.stream_key
        return "****" + self.stream_key[-4:]
    
    def get_full_stream_key(self) -> str:
        """Get full stream key (untuk internal use only)"""
        return self.stream_key
