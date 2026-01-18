"""
MusicFile model untuk tracking music files dengan metadata.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class MusicFile(Base):
    """Model untuk music file dengan metadata lengkap"""
    __tablename__ = "music_files"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, unique=True, nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=True)
    file_size = Column(Integer, nullable=False)  # in bytes
    duration = Column(Float, nullable=True)  # in seconds
    format = Column(String, nullable=False)  # mp3, aac, m4a, etc.
    tags = Column(JSON, default=list, nullable=False)  # array of strings
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used = Column(DateTime, nullable=True)
    
    # Relationship
    category = relationship("Category", backref="music_files")
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'filename': self.filename,
            'file_path': self.file_path,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else None,
            'category_color': self.category.color if self.category else None,
            'file_size': self.file_size,
            'duration': self.duration,
            'format': self.format,
            'tags': self.tags,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'last_used': self.last_used.isoformat() if self.last_used else None
        }
    
    def format_file_size(self) -> str:
        """Format file size to human readable"""
        units = ['B', 'KB', 'MB', 'GB']
        size = self.file_size
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        return f"{size:.2f} {units[unit_index]}"
    
    def format_duration(self) -> str:
        """Format duration to MM:SS"""
        if not self.duration:
            return "Unknown"
        
        minutes = int(self.duration // 60)
        seconds = int(self.duration % 60)
        return f"{minutes}:{seconds:02d}"
    
    def __repr__(self):
        return f"<MusicFile(id={self.id}, filename='{self.filename}')>"
