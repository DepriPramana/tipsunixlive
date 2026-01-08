"""
Service untuk mengelola live streaming history.
"""
import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import datetime
from app.models.live_history import LiveHistory
from app.config import YOUTUBE_STREAM_KEY

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LiveHistoryService:
    """Service untuk mengelola live streaming history"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_session(
        self,
        mode: str,
        video_id: Optional[int] = None,
        playlist_id: Optional[int] = None,
        max_duration_hours: int = 0
    ) -> LiveHistory:
        """
        Create new live streaming session.
        
        Args:
            mode: Mode streaming ('single' atau 'playlist')
            video_id: ID video (untuk mode single)
            playlist_id: ID playlist (untuk mode playlist)
            
        Returns:
            LiveHistory object yang baru dibuat
        """
        logger.info(f"Creating live session: mode={mode}, video_id={video_id}, playlist_id={playlist_id}")
        
        session = LiveHistory(
            mode=mode,
            video_id=video_id,
            playlist_id=playlist_id,
            status='running',
            stream_key=YOUTUBE_STREAM_KEY,
            start_time=datetime.utcnow(),
            max_duration_hours=max_duration_hours
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        logger.info(f"✅ Live session created with ID: {session.id}")
        return session
    
    def end_session(
        self,
        session_id: int,
        status: str = 'success',
        error_message: Optional[str] = None
    ) -> Optional[LiveHistory]:
        """
        End live streaming session.
        
        Args:
            session_id: ID session yang akan diakhiri
            status: Status akhir ('success', 'stopped', 'failed')
            error_message: Pesan error jika status failed
            
        Returns:
            Updated LiveHistory object atau None jika tidak ditemukan
        """
        session = self.db.query(LiveHistory).filter(LiveHistory.id == session_id).first()
        
        if not session:
            logger.error(f"Session {session_id} tidak ditemukan")
            return None
        
        session.end_time = datetime.utcnow()
        session.status = status
        
        if error_message:
            session.error_message = error_message
        
        self.db.commit()
        self.db.refresh(session)
        
        duration = session.get_duration_formatted()
        logger.info(f"✅ Session {session_id} ended: status={status}, duration={duration}")
        
        return session
    
    def get_active_session(self) -> Optional[LiveHistory]:
        """
        Get currently active streaming session.
        
        Returns:
            Active LiveHistory object atau None
        """
        return self.db.query(LiveHistory).filter(
            LiveHistory.status == 'running'
        ).order_by(LiveHistory.start_time.desc()).first()
    
    def get_session(self, session_id: int) -> Optional[LiveHistory]:
        """Get session by ID"""
        return self.db.query(LiveHistory).filter(LiveHistory.id == session_id).first()
    
    def get_all_sessions(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List:
        """
        Get all sessions from both LiveHistory and LiveSession.
        """
        from app.models.live_session import LiveSession
        
        # Query LiveHistory
        history_query = self.db.query(LiveHistory)
        if status:
            history_query = history_query.filter(LiveHistory.status == status)
        history_items = history_query.all()
        
        # Query LiveSession (only stopped or failed sessions for "history", 
        # but sometimes folks want to see running ones too)
        session_query = self.db.query(LiveSession)
        if status:
            session_query = session_query.filter(LiveSession.status == status)
        session_items = session_query.all()
        
        # Merge and sort
        combined = history_items + session_items
        combined.sort(key=lambda x: x.start_time or datetime.min, reverse=True)
        
        # Apply pagination
        return combined[skip : skip+limit]
    
    def get_playlist_sessions(self, playlist_id: int) -> List[LiveHistory]:
        """Get all sessions untuk playlist tertentu"""
        return self.db.query(LiveHistory).filter(
            LiveHistory.playlist_id == playlist_id
        ).order_by(LiveHistory.start_time.desc()).all()
    
    def get_video_sessions(self, video_id: int) -> List[LiveHistory]:
        """Get all sessions untuk video tertentu"""
        return self.db.query(LiveHistory).filter(
            LiveHistory.video_id == video_id
        ).order_by(LiveHistory.start_time.desc()).all()
    
    def get_statistics(self) -> dict:
        """
        Get streaming statistics from both legacy and new sessions.
        """
        from app.models.live_session import LiveSession
        
        # Legacy counts
        h_total = self.db.query(LiveHistory).count()
        h_success = self.db.query(LiveHistory).filter(LiveHistory.status == 'success').count()
        h_failed = self.db.query(LiveHistory).filter(LiveHistory.status == 'failed').count()
        h_active = self.db.query(LiveHistory).filter(LiveHistory.status == 'running').count()
        
        # New counts
        s_total = self.db.query(LiveSession).count()
        s_success = self.db.query(LiveSession).filter(LiveSession.status == 'stopped').count()
        s_failed = self.db.query(LiveSession).filter(LiveSession.status == 'failed').count()
        s_active = self.db.query(LiveSession).filter(LiveSession.status == 'running').count()
        
        total_sessions = h_total + s_total
        success_sessions = h_success + s_success
        failed_sessions = h_failed + s_failed
        active_sessions = h_active + s_active
        
        return {
            "total_sessions": total_sessions,
            "success_sessions": success_sessions,
            "failed_sessions": failed_sessions,
            "active_sessions": active_sessions,
            "success_rate": (success_sessions / total_sessions * 100) if total_sessions > 0 else 0
        }
