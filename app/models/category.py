"""
Category model untuk mengorganisir music files.
"""
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database import Base


class Category(Base):
    """Model untuk kategori musik (Lofi, Jazz, Classical, etc.)"""
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    color = Column(String, default="#6c757d", nullable=False)  # Hex color for UI
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'color': self.color,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}')>"
