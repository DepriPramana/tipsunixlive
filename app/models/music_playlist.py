"""
Model untuk mengelola music playlist dengan video background.
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Float
from app.database import Base
from datetime import datetime


class MusicPlaylist(Base):
    """
    Model untuk mengelola playlist musik dengan video background looping.
    
    Berbeda dengan Playlist biasa yang berisi multiple videos,
    MusicPlaylist berisi:
    - 1 video background yang akan di-loop
    - Multiple audio files (musik) yang akan diputar
    
    Attributes:
        id: Primary key
        name: Nama playlist
        video_background_path: Path ke video background yang akan di-loop
        music_files: List path file musik dalam format JSON array
        mode: Mode pemutaran ('sequence' atau 'random')
        created_at: Timestamp pembuatan playlist
    """
    __tablename__ = "music_playlists"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    video_background_path = Column(String, nullable=False)  # Path ke video background
    music_files = Column(JSON, default=list, nullable=False)  # List of music file paths
    mode = Column(String, default="sequence", nullable=False)  # 'random' atau 'sequence'
    
    # Sound Effect (Ambient)
    sound_effect_path = Column(String, nullable=True)  # Path file sound effect looping
    sound_effect_volume = Column(Float, default=0.3, nullable=False)  # Volume (0.0 - 1.0)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<MusicPlaylist(id={self.id}, name='{self.name}', mode='{self.mode}')>"
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "video_background_path": self.video_background_path,
            "music_files": self.music_files,
            "mode": self.mode,
            "sound_effect_path": self.sound_effect_path,
            "sound_effect_volume": self.sound_effect_volume,
            "music_count": len(self.music_files) if self.music_files else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
