"""
Video model untuk menyimpan metadata video.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime
from app.database import Base
from datetime import datetime

class Video(Base):
    """
    Model untuk menyimpan informasi video.
    
    Attributes:
        id: Primary key
        name: Nama video
        path: Path ke file video
        duration: Duration dalam format HH:MM:SS
        duration_seconds: Duration dalam detik
        resolution: Resolution (e.g., "1920x1080")
        width: Video width
        height: Video height
        codec: Video codec (e.g., "h264")
        fps: Frame rate
        bitrate: Video bitrate
        file_size: File size dalam bytes
        format: Container format
        audio_codec: Audio codec
        source: Source video (uploaded/downloaded/gdrive)
        created_at: Timestamp pembuatan record
    """
    __tablename__ = "videos"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Basic info
    name = Column(String, nullable=False)
    path = Column(String, nullable=False, unique=True)
    source = Column(String, default="uploaded")  # uploaded, downloaded, gdrive
    thumbnail_path = Column(String, nullable=True)
    
    # Duration
    duration = Column(String)  # Format: HH:MM:SS
    duration_seconds = Column(Float, default=0.0)
    
    # Video properties
    resolution = Column(String)  # e.g., "1920x1080"
    width = Column(Integer, default=0)
    height = Column(Integer, default=0)
    codec = Column(String)  # e.g., "h264"
    fps = Column(Float, default=0.0)
    bitrate = Column(Integer, default=0)
    
    # File info
    file_size = Column(Integer, default=0)  # bytes
    format = Column(String)  # Container format
    
    # Audio
    audio_codec = Column(String)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Video(id={self.id}, name='{self.name}', resolution='{self.resolution}')>"
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "source": self.source,
            "thumbnail_path": self.thumbnail_path,
            "duration": self.duration,
            "duration_seconds": self.duration_seconds,
            "resolution": self.resolution,
            "width": self.width,
            "height": self.height,
            "codec": self.codec,
            "fps": self.fps,
            "bitrate": self.bitrate,
            "file_size": self.file_size,
            "format": self.format,
            "audio_codec": self.audio_codec,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

