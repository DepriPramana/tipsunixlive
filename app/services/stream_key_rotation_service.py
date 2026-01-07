"""
Stream Key Rotation Service.
Automatic fallback when stream key fails.
"""
import logging
from typing import Optional, Dict
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import SessionLocal
from app.models.stream_key import StreamKey
from app.models.live_session import LiveSession
from app.services.ffmpeg_service import ffmpeg_service
from app.services.stream_control_service import stream_control

logger = logging.getLogger(__name__)


class StreamKeyRotationService:
    """Service for automatic stream key rotation"""
    
    def __init__(self):
        self.rotation_history = []
    
    def detect_stream_error(self, session_id: int, db: Session) -> bool:
        """
        Detect if stream has error.
        
        Checks:
        1. FFmpeg process still running?
        2. Stream duration too short? (< 30 seconds = likely error)
        3. Status = failed?
        
        Args:
            session_id: LiveSession ID
            db: Database session
            
        Returns:
            True if error detected
        """
        
        session = db.query(LiveSession).filter(
            LiveSession.id == session_id
        ).first()
        
        if not session:
            logger.error(f"Session {session_id} not found")
            return False
        
        # Check 1: Process still running?
        if session.ffmpeg_pid:
            import psutil
            try:
                process = psutil.Process(session.ffmpeg_pid)
                if not process.is_running():
                    logger.warning(f"Session {session_id}: FFmpeg process not running")
                    return True
            except psutil.NoSuchProcess:
                logger.warning(f"Session {session_id}: FFmpeg process does not exist")
                return True
        
        # Check 2: Duration too short?
        if session.start_time:
            duration = (datetime.utcnow() - session.start_time).total_seconds()
            if duration < 30 and session.status == 'stopped':
                logger.warning(f"Session {session_id}: Stream stopped too quickly ({duration}s)")
                return True
        
        # Check 3: Status failed?
        if session.status == 'failed':
            logger.warning(f"Session {session_id}: Status is failed")
            return True
        
        return False
    
    def get_fallback_stream_key(
        self,
        current_key_id: int,
        db: Session
    ) -> Optional[StreamKey]:
        """
        Get fallback stream key.
        
        Strategy:
        1. Get all active stream keys
        2. Exclude current key
        3. Exclude keys currently in use
        4. Return first available
        
        Args:
            current_key_id: Current stream key ID
            db: Database session
            
        Returns:
            Fallback StreamKey or None
        """
        
        # Get all active keys
        active_keys = db.query(StreamKey).filter(
            StreamKey.is_active == True,
            StreamKey.id != current_key_id
        ).all()
        
        if not active_keys:
            logger.error("No fallback stream keys available")
            return None
        
        # Get currently used keys
        active_sessions = db.query(LiveSession).filter(
            LiveSession.status == 'running'
        ).all()
        
        used_key_ids = set(s.stream_key_id for s in active_sessions)
        
        # Find available key
        for key in active_keys:
            if key.id not in used_key_ids:
                logger.info(f"Found fallback key: {key.name} (ID: {key.id})")
                return key
        
        logger.warning("All fallback keys are in use")
        return None
    
    def rotate_stream_key(
        self,
        session_id: int,
        db: Session
    ) -> Dict:
        """
        Rotate stream key for a session.
        
        Process:
        1. Detect error
        2. Get fallback key
        3. Stop current FFmpeg
        4. Update session with new key
        5. Restart FFmpeg with new key
        6. Log rotation
        
        Args:
            session_id: LiveSession ID
            db: Database session
            
        Returns:
            Rotation result
        """
        
        logger.info(f"[ROTATION] Starting rotation for session {session_id}")
        
        # Step 1: Get session
        session = db.query(LiveSession).filter(
            LiveSession.id == session_id
        ).first()
        
        if not session:
            error = f"Session {session_id} not found"
            logger.error(f"[ROTATION] {error}")
            return {'success': False, 'error': error}
        
        current_key_id = session.stream_key_id
        current_key = session.stream_key
        
        logger.info(f"[ROTATION] Current key: {current_key.name if current_key else 'N/A'}")
        
        # Step 2: Get fallback key
        fallback_key = self.get_fallback_stream_key(current_key_id, db)
        
        if not fallback_key:
            error = "No fallback stream key available"
            logger.error(f"[ROTATION] {error}")
            return {'success': False, 'error': error}
        
        logger.info(f"[ROTATION] Fallback key: {fallback_key.name}")
        
        # Step 3: Stop current FFmpeg
        logger.info(f"[ROTATION] Stopping current FFmpeg (PID: {session.ffmpeg_pid})")
        
        if session.ffmpeg_pid:
            try:
                stream_control.stop_stream_by_session_id(db, session_id)
                logger.info(f"[ROTATION] FFmpeg stopped successfully")
            except Exception as e:
                logger.warning(f"[ROTATION] Error stopping FFmpeg: {e}")
        
        # Step 4: Update session with new key
        session.stream_key_id = fallback_key.id
        session.status = 'starting'
        db.commit()
        
        logger.info(f"[ROTATION] Session updated with new key")
        
        # Step 5: Get video paths
        video_paths = []
        
        if session.mode == 'single' and session.video:
            video_paths = [session.video.path]
        elif session.mode == 'playlist' and session.playlist:
            from app.services.playlist_service import PlaylistService
            playlist_service = PlaylistService(db)
            video_paths = playlist_service.get_video_paths(
                session.playlist_id,
                shuffle=(session.playlist.mode == 'random')
            )
        
        if not video_paths:
            error = "No video paths available"
            logger.error(f"[ROTATION] {error}")
            session.status = 'failed'
            db.commit()
            return {'success': False, 'error': error}
        
        # Step 6: Restart FFmpeg with new key
        logger.info(f"[ROTATION] Restarting FFmpeg with new key")
        
        try:
            process = ffmpeg_service.start_stream(
                session_id=session.id,
                video_paths=video_paths,
                stream_key=fallback_key.get_full_key(),
                loop=True,
                mode=session.mode
            )
            
            if not process:
                raise Exception("Failed to start FFmpeg")
            
            # Update session
            session.ffmpeg_pid = process.pid
            session.status = 'running'
            session.start_time = datetime.utcnow()
            db.commit()
            
            logger.info(f"[ROTATION] FFmpeg restarted (PID: {process.pid})")
            
            # Step 7: Log rotation
            rotation_log = {
                'timestamp': datetime.utcnow().isoformat(),
                'session_id': session_id,
                'old_key_id': current_key_id,
                'old_key_name': current_key.name if current_key else 'N/A',
                'new_key_id': fallback_key.id,
                'new_key_name': fallback_key.name,
                'new_ffmpeg_pid': process.pid
            }
            
            self.rotation_history.append(rotation_log)
            
            logger.info(f"[ROTATION] ✅ Rotation successful!")
            logger.info(f"[ROTATION]    Old: {current_key.name if current_key else 'N/A'}")
            logger.info(f"[ROTATION]    New: {fallback_key.name}")
            logger.info(f"[ROTATION]    PID: {process.pid}")
            
            return {
                'success': True,
                'session_id': session_id,
                'old_key': {
                    'id': current_key_id,
                    'name': current_key.name if current_key else 'N/A'
                },
                'new_key': {
                    'id': fallback_key.id,
                    'name': fallback_key.name
                },
                'new_ffmpeg_pid': process.pid,
                'message': f"Stream key rotated from '{current_key.name if current_key else 'N/A'}' to '{fallback_key.name}'"
            }
            
        except Exception as e:
            error = f"Error restarting FFmpeg: {str(e)}"
            logger.error(f"[ROTATION] {error}")
            
            session.status = 'failed'
            db.commit()
            
            return {'success': False, 'error': error}
    
    def auto_rotate_on_error(
        self,
        session_id: int,
        db: Session
    ) -> Dict:
        """
        Automatically rotate if error detected.
        
        Args:
            session_id: LiveSession ID
            db: Database session
            
        Returns:
            Rotation result
        """
        
        # Detect error
        has_error = self.detect_stream_error(session_id, db)
        
        if not has_error:
            logger.info(f"[AUTO-ROTATE] Session {session_id}: No error detected")
            return {
                'success': True,
                'rotated': False,
                'message': 'No error detected, rotation not needed'
            }
        
        logger.warning(f"[AUTO-ROTATE] Session {session_id}: Error detected, rotating...")
        
        # Rotate
        result = self.rotate_stream_key(session_id, db)
        result['rotated'] = result.get('success', False)
        
        return result
    
    def get_rotation_history(self) -> list:
        """Get rotation history"""
        return self.rotation_history


# Global instance
stream_key_rotation = StreamKeyRotationService()
