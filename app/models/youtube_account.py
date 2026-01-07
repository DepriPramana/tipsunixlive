from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from app.database import Base

class YouTubeAccount(Base):
    """
    Model for storing YouTube account/channel OAuth2 metadata.
    Allows managing multiple channels with separate tokens.
    """
    __tablename__ = "youtube_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Friendly name (e.g., "Main Channel")
    channel_id = Column(String, unique=True, index=True, nullable=True)
    channel_title = Column(String, nullable=True)
    email = Column(String, nullable=True)
    token_filename = Column(String, unique=True, nullable=False) # e.g., "token_123.pickle"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_authenticated_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'channel_id': self.channel_id,
            'channel_title': self.channel_title,
            'email': self.email,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_authenticated_at': self.last_authenticated_at.isoformat() if self.last_authenticated_at else None
        }
