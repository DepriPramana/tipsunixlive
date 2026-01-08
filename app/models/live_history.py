"""
LiveHistory model untuk tracking streaming sessions.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

class LiveHistory(Base):
    """
    Model untuk tracking history live streaming.
    Mendukung multiple concurrent streams per channel.
    
    Attributes:
        id: Primary key
        stream_key_id: ID stream key yang digunakan (FK to stream_keys)
        video_id: ID video yang di-stream (untuk mode single)
        playlist_id: ID playlist yang di-stream (untuk mode playlist)
        mode: Mode streaming ('single' atau 'playlist')
        stream_title: Judul stream (custom title)
        start_time: Waktu mulai streaming
        end_time: Waktu selesai streaming
        status: Status streaming ('running', 'success', 'stopped', 'failed')
        ffmpeg_pid: Process ID FFmpeg
        stream_key: YouTube stream key yang digunakan (masked)
        error_message: Pesan error jika status failed
        created_at: Timestamp pembuatan record
    """
    __tablename__ = "live_history"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Stream key reference (NEW)
    stream_key_id = Column(Integer, ForeignKey('stream_keys.id'), nullable=True, index=True)
    
    # Video/Playlist reference
    video_id = Column(Integer, ForeignKey('videos.id'), nullable=True)
    playlist_id = Column(Integer, ForeignKey('playlists.id'), nullable=True)
    
    # Mode streaming
    mode = Column(String, nullable=False)  # 'single' atau 'playlist'
    
    # Stream info (NEW)
    stream_title = Column(String, nullable=True)  # Custom stream title
    ffmpeg_pid = Column(Integer, nullable=True)  # FFmpeg process ID
    
    # Timestamps
    start_time = Column(DateTime, default=datetime.now, nullable=False)
    end_time = Column(DateTime, nullable=True)
    
    # Status
    status = Column(String, default='running', nullable=False)  # running, success, stopped, failed
    
    # Stream info
    stream_key = Column(String, nullable=True)  # YouTube stream key (masked)
    error_message = Column(String, nullable=True)  # Error message jika failed
    max_duration_hours = Column(Integer, default=0, nullable=True)  # Max duration in hours
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    stream_key_rel = relationship("StreamKey", backref="live_histories")
    video = relationship("Video", backref="live_histories")
    playlist = relationship("Playlist", backref="live_histories")
    
    def __repr__(self):
        return f"<LiveHistory(id={self.id}, stream_key_id={self.stream_key_id}, mode='{self.mode}', status='{self.status}')>"
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "stream_key_id": self.stream_key_id,
            "stream_key_name": self.stream_key_rel.name if self.stream_key_rel else None,
            "video_id": self.video_id,
            "playlist_id": self.playlist_id,
            "mode": self.mode,
            "stream_title": self.stream_title,
            "ffmpeg_pid": self.ffmpeg_pid,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "stream_key": self._mask_stream_key(self.stream_key) if self.stream_key else None,
            "error_message": self.error_message,
            "max_duration_hours": self.max_duration_hours,
            "youtube_id": self.youtube_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "duration_seconds": self._calculate_duration(),
            "duration_formatted": self.get_duration_formatted()
        }
    
    def _mask_stream_key(self, key: str) -> str:
        """Mask stream key untuk security (show only last 4 chars)"""
        if not key or len(key) < 8:
            return "****"
        return f"****{key[-4:]}"
    
    def _calculate_duration(self) -> float:
        """Calculate streaming duration in seconds"""
        if not self.start_time:
            return 0.0
        
        end = self.end_time if self.end_time else datetime.now()
        duration = (end - self.start_time).total_seconds()
        return duration
    
    def get_duration_seconds(self) -> float:
        """Alias for compatibility with LiveSession"""
        return self._calculate_duration()
    
    def get_duration_formatted(self) -> str:
        """Get formatted duration (HH:MM:SS)"""
        seconds = self._calculate_duration()
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

