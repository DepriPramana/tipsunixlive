"""
Service untuk mengelola YouTube broadcasts.
"""
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from app.models.youtube_broadcast import YouTubeBroadcast
import logging

logger = logging.getLogger(__name__)


class YouTubeBroadcastService:
    """Service untuk mengelola YouTube broadcasts"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_broadcast(
        self,
        broadcast_id: str,
        stream_id: str,
        stream_key: str,
        rtmp_url: str,
        ingestion_address: str,
        title: str,
        description: str,
        broadcast_url: str,
        privacy_status: str = 'public',
        resolution: str = '1080p',
        frame_rate: str = '30fps',
        scheduled_start_time: Optional[datetime] = None
    ) -> YouTubeBroadcast:
        """
        Create new YouTube broadcast record.
        
        Args:
            broadcast_id: YouTube broadcast ID
            stream_id: YouTube stream ID
            stream_key: Stream key untuk FFmpeg
            rtmp_url: Full RTMP URL
            ingestion_address: RTMP ingestion address
            title: Broadcast title
            description: Broadcast description
            broadcast_url: YouTube watch URL
            privacy_status: Privacy status
            resolution: Video resolution
            frame_rate: Video frame rate
            scheduled_start_time: Scheduled start time
            
        Returns:
            YouTubeBroadcast object
        """
        broadcast = YouTubeBroadcast(
            broadcast_id=broadcast_id,
            stream_id=stream_id,
            stream_key=stream_key,
            rtmp_url=rtmp_url,
            ingestion_address=ingestion_address,
            title=title,
            description=description,
            broadcast_url=broadcast_url,
            privacy_status=privacy_status,
            resolution=resolution,
            frame_rate=frame_rate,
            scheduled_start_time=scheduled_start_time,
            status='ready'
        )
        
        self.db.add(broadcast)
        self.db.commit()
        self.db.refresh(broadcast)
        
        logger.info(f"✅ YouTube broadcast saved to DB: {broadcast_id}")
        
        return broadcast
    
    def get_broadcast(self, broadcast_id: str) -> Optional[YouTubeBroadcast]:
        """Get broadcast by YouTube broadcast ID"""
        return self.db.query(YouTubeBroadcast).filter(
            YouTubeBroadcast.broadcast_id == broadcast_id
        ).first()
    
    def get_broadcast_by_db_id(self, db_id: int) -> Optional[YouTubeBroadcast]:
        """Get broadcast by database ID"""
        return self.db.query(YouTubeBroadcast).filter(
            YouTubeBroadcast.id == db_id
        ).first()
    
    def update_status(
        self,
        broadcast_id: str,
        status: str,
        actual_start_time: Optional[datetime] = None,
        actual_end_time: Optional[datetime] = None
    ) -> Optional[YouTubeBroadcast]:
        """
        Update broadcast status.
        
        Args:
            broadcast_id: YouTube broadcast ID
            status: New status (ready, live, complete, error)
            actual_start_time: Actual start time
            actual_end_time: Actual end time
            
        Returns:
            Updated broadcast or None
        """
        broadcast = self.get_broadcast(broadcast_id)
        
        if not broadcast:
            logger.error(f"Broadcast {broadcast_id} not found")
            return None
        
        broadcast.status = status
        
        if actual_start_time:
            broadcast.actual_start_time = actual_start_time
        
        if actual_end_time:
            broadcast.actual_end_time = actual_end_time
        
        self.db.commit()
        self.db.refresh(broadcast)
        
        logger.info(f"✅ Broadcast {broadcast_id} status updated to: {status}")
        
        return broadcast
    
    def get_all_broadcasts(
        self,
        skip: int = 0,
        limit: int = 10,
        status: Optional[str] = None
    ) -> List[YouTubeBroadcast]:
        """Get all broadcasts with optional filter"""
        query = self.db.query(YouTubeBroadcast)
        
        if status:
            query = query.filter(YouTubeBroadcast.status == status)
        
        return query.order_by(
            YouTubeBroadcast.created_at.desc()
        ).offset(skip).limit(limit).all()
    
    def link_to_live_history(
        self,
        broadcast_id: str,
        live_history_id: int
    ) -> Optional[YouTubeBroadcast]:
        """Link broadcast to live history session"""
        broadcast = self.get_broadcast(broadcast_id)
        
        if not broadcast:
            return None
        
        broadcast.live_history_id = live_history_id
        self.db.commit()
        self.db.refresh(broadcast)
        
        logger.info(f"✅ Broadcast {broadcast_id} linked to LiveHistory {live_history_id}")
        
        return broadcast
