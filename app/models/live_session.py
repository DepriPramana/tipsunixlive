"""
LiveSession model untuk tracking multiple concurrent streams.
Mendukung relasi dengan StreamKey, Video, dan Playlist.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class LiveSession(Base):
    """Model untuk live streaming session"""
    __tablename__ = "live_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign Keys
    stream_key_id = Column(Integer, ForeignKey('stream_keys.id'), nullable=False, index=True)
    video_id = Column(Integer, ForeignKey('videos.id'), nullable=True)
    playlist_id = Column(Integer, ForeignKey('playlists.id'), nullable=True)
    
    # Stream info
    mode = Column(String, nullable=False)  # 'single' or 'playlist'
    status = Column(String, default='running', nullable=False)  # running, stopped, failed
    
    # Process info
    ffmpeg_pid = Column(Integer, nullable=True)  # FFmpeg process ID
    
    # Timestamps
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)
    
    # Auto-recovery
    restart_count = Column(Integer, default=0, nullable=False)
    last_error = Column(String, nullable=True)
    
    # Advanced features
    youtube_id = Column(String, nullable=True)  # YouTube Video ID for preview
    max_duration_hours = Column(Integer, nullable=True)  # Max duration in hours (0 or null = unlimited)
    
    # Relationships
    stream_key = relationship("StreamKey", backref="live_sessions")
    video = relationship("Video", backref="live_sessions")
    playlist = relationship("Playlist", backref="live_sessions")
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'stream_key_id': self.stream_key_id,
            'stream_key_name': self.stream_key.name if self.stream_key else None,
            'video_id': self.video_id,
            'playlist_id': self.playlist_id,
            'mode': self.mode,
            'ffmpeg_pid': self.ffmpeg_pid,
            'start_time': self.start_time.isoformat() + "Z" if self.start_time else None,
            'end_time': self.end_time.isoformat() + "Z" if self.end_time else None,
            'status': self.status,
            'restart_count': self.restart_count,
            'last_error': self.last_error,
            'youtube_id': self.youtube_id,
            'max_duration_hours': self.max_duration_hours,
            'duration_seconds': self.get_duration_seconds(),
            'is_active': self.is_active()
        }
    
    def get_duration_seconds(self) -> float:
        """Calculate session duration in seconds"""
        if not self.start_time:
            return 0
        
        end = self.end_time or datetime.utcnow()
        return (end - self.start_time).total_seconds()
    
    def get_duration_formatted(self) -> str:
        """Get formatted duration (HH:MM:SS)"""
        seconds = int(self.get_duration_seconds())
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def is_active(self) -> bool:
        """Check if session is currently active"""
        return self.status == 'running' and self.end_time is None
    
    def __repr__(self):
        return f"<LiveSession(id={self.id}, mode='{self.mode}', status='{self.status}', pid={self.ffmpeg_pid})>"
