"""
Scheduled Live Session model untuk menyimpan jadwal live streaming.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from datetime import datetime
from app.database import Base


class ScheduledLive(Base):
    """Model untuk scheduled live streaming"""
    __tablename__ = "scheduled_lives"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign Keys
    stream_key_id = Column(Integer, ForeignKey('stream_keys.id'), nullable=False)
    video_id = Column(Integer, ForeignKey('videos.id'), nullable=True)
    playlist_id = Column(Integer, ForeignKey('playlists.id'), nullable=True)
    
    # Schedule info
    scheduled_time = Column(DateTime, nullable=False)
    mode = Column(String, nullable=False)  # 'single' or 'playlist'
    loop = Column(Boolean, default=True)
    recurrence = Column(String, default='none')  # none, daily, weekly
    
    # Job info
    job_id = Column(String, unique=True, nullable=True)  # APScheduler job ID
    
    # Status
    status = Column(String, default='pending')  # pending, running, completed, failed, cancelled
    
    # Execution tracking
    live_session_id = Column(Integer, ForeignKey('live_sessions.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Error tracking
    error_message = Column(String, nullable=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'stream_key_id': self.stream_key_id,
            'video_id': self.video_id,
            'playlist_id': self.playlist_id,
            'scheduled_time': self.scheduled_time.isoformat() if self.scheduled_time else None,
            'mode': self.mode,
            'loop': self.loop,
            'recurrence': self.recurrence,
            'job_id': self.job_id,
            'status': self.status,
            'live_session_id': self.live_session_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message
        }
    
    def __repr__(self):
        return f"<ScheduledLive(id={self.id}, scheduled_time={self.scheduled_time}, status='{self.status}')>"
