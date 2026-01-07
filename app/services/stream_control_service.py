"""
Stream Control Service untuk mengelola live streaming.
Menangani start, stop, dan monitoring streams dengan aman.
"""
import logging
import psutil
from typing import Optional, Dict
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.live_session import LiveSession
from app.models.stream_key import StreamKey
from app.services.ffmpeg_service import ffmpeg_service

logger = logging.getLogger(__name__)


class StreamControlService:
    """Service untuk control live streaming"""
    
    def stop_stream_by_session_id(
        self,
        db: Session,
        session_id: int,
        force: bool = False
    ) -> Dict:
        """
        Stop stream berdasarkan session ID.
        
        Args:
            db: Database session
            session_id: LiveSession ID
            force: Force kill jika True
            
        Returns:
            Dictionary dengan hasil operasi
        """
        
        logger.info(f"Stopping stream for session {session_id}")
        
        # Get session from database
        session = db.query(LiveSession).filter(
            LiveSession.id == session_id
        ).first()
        
        if not session:
            logger.error(f"Session {session_id} not found")
            return {
                'success': False,
                'error': 'Session not found'
            }
        
        # Check if already stopped
        if session.status in ['stopped', 'failed']:
            logger.warning(f"Session {session_id} already {session.status}")
            return {
                'success': True,
                'message': f'Session already {session.status}',
                'session_id': session_id
            }
        
        # Stop FFmpeg process
        ffmpeg_stopped = False
        
        if session.ffmpeg_pid:
            ffmpeg_stopped = self._kill_ffmpeg_process(
                session.ffmpeg_pid,
                force=force
            )
        
        # Stop via ffmpeg_service
        service_stopped = ffmpeg_service.stop_stream(session_id)
        
        # Update database
        session.status = 'stopped'
        session.end_time = datetime.utcnow()
        db.commit()
        
        logger.info(f"[OK] Stream stopped for session {session_id}")
        
        return {
            'success': True,
            'session_id': session_id,
            'ffmpeg_stopped': ffmpeg_stopped,
            'service_stopped': service_stopped,
            'duration': session.get_duration_formatted()
        }
    
    def stop_stream_by_stream_key_id(
        self,
        db: Session,
        stream_key_id: int,
        stop_all: bool = True
    ) -> Dict:
        """
        Stop stream(s) berdasarkan stream key ID.
        
        Args:
            db: Database session
            stream_key_id: StreamKey ID
            stop_all: Stop semua session dengan key ini jika True
            
        Returns:
            Dictionary dengan hasil operasi
        """
        
        logger.info(f"Stopping stream(s) for stream_key_id {stream_key_id}")
        
        # Get stream key
        stream_key = db.query(StreamKey).filter(
            StreamKey.id == stream_key_id
        ).first()
        
        if not stream_key:
            logger.error(f"Stream key {stream_key_id} not found")
            return {
                'success': False,
                'error': 'Stream key not found'
            }
        
        # Get active sessions with this stream key
        query = db.query(LiveSession).filter(
            LiveSession.stream_key_id == stream_key_id,
            LiveSession.status == 'running'
        )
        
        if not stop_all:
            query = query.limit(1)
        
        sessions = query.all()
        
        if not sessions:
            logger.warning(f"No active sessions found for stream_key_id {stream_key_id}")
            return {
                'success': True,
                'message': 'No active sessions found',
                'stopped_count': 0
            }
        
        # Stop all sessions
        stopped_sessions = []
        
        for session in sessions:
            result = self.stop_stream_by_session_id(db, session.id)
            if result['success']:
                stopped_sessions.append(session.id)
        
        logger.info(f"[OK] Stopped {len(stopped_sessions)} session(s) for stream_key_id {stream_key_id}")
        
        return {
            'success': True,
            'stream_key_id': stream_key_id,
            'stream_key_name': stream_key.name,
            'stopped_count': len(stopped_sessions),
            'stopped_sessions': stopped_sessions
        }
    
    def _kill_ffmpeg_process(
        self,
        pid: int,
        force: bool = False
    ) -> bool:
        """
        Kill FFmpeg process dengan aman.
        
        Args:
            pid: Process ID
            force: Force kill jika True
            
        Returns:
            True jika berhasil
        """
        
        try:
            # Check if process exists
            if not psutil.pid_exists(pid):
                logger.warning(f"Process {pid} does not exist")
                return True  # Already dead
            
            # Get process
            process = psutil.Process(pid)
            
            # Check if it's actually FFmpeg
            process_name = process.name().lower()
            if 'ffmpeg' not in process_name:
                logger.warning(f"Process {pid} is not FFmpeg (name: {process_name})")
                # Continue anyway, might be renamed
            
            logger.info(f"Killing FFmpeg process {pid}")
            
            if force:
                # Force kill immediately
                process.kill()
                logger.info(f"[OK] Force killed process {pid}")
            else:
                # Graceful termination
                process.terminate()
                
                # Wait for process to terminate
                try:
                    process.wait(timeout=5)
                    logger.info(f"[OK] Process {pid} terminated gracefully")
                except psutil.TimeoutExpired:
                    logger.warning(f"Process {pid} didn't terminate, force killing")
                    process.kill()
                    process.wait(timeout=3)
                    logger.info(f"[OK] Force killed process {pid}")
            
            # Cleanup zombie processes
            self._cleanup_zombie_process(pid)
            
            return True
            
        except psutil.NoSuchProcess:
            logger.info(f"Process {pid} already terminated")
            return True
        except psutil.AccessDenied:
            logger.error(f"Access denied to kill process {pid}")
            return False
        except Exception as e:
            logger.error(f"Error killing process {pid}: {e}")
            return False
    
    def _cleanup_zombie_process(self, pid: int):
        """
        Cleanup zombie process.
        
        Args:
            pid: Process ID
        """
        
        try:
            if not psutil.pid_exists(pid):
                return
            
            process = psutil.Process(pid)
            
            # Check if zombie
            if process.status() == psutil.STATUS_ZOMBIE:
                logger.warning(f"Process {pid} is zombie, attempting cleanup")
                
                # Try to get parent and wait
                try:
                    parent = process.parent()
                    if parent:
                        # Parent should reap the zombie
                        import os
                        os.waitpid(pid, os.WNOHANG)
                        logger.info(f"[OK] Zombie process {pid} cleaned up")
                except:
                    pass
        
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            logger.error(f"Error cleaning up zombie process {pid}: {e}")
    
    def stop_all_active_streams(self, db: Session) -> Dict:
        """
        Stop semua active streams.
        
        Args:
            db: Database session
            
        Returns:
            Dictionary dengan hasil operasi
        """
        
        logger.info("Stopping all active streams")
        
        # Get all running sessions
        sessions = db.query(LiveSession).filter(
            LiveSession.status == 'running'
        ).all()
        
        if not sessions:
            logger.info("No active sessions found")
            return {
                'success': True,
                'message': 'No active sessions',
                'stopped_count': 0
            }
        
        # Stop all
        stopped_sessions = []
        failed_sessions = []
        
        for session in sessions:
            result = self.stop_stream_by_session_id(db, session.id)
            if result['success']:
                stopped_sessions.append(session.id)
            else:
                failed_sessions.append(session.id)
        
        logger.info(f"[OK] Stopped {len(stopped_sessions)} sessions, {len(failed_sessions)} failed")
        
        return {
            'success': True,
            'stopped_count': len(stopped_sessions),
            'failed_count': len(failed_sessions),
            'stopped_sessions': stopped_sessions,
            'failed_sessions': failed_sessions
        }
    
    def force_cleanup_orphaned_processes(self, db: Session) -> Dict:
        """
        Force cleanup orphaned FFmpeg processes.
        Mencari FFmpeg process yang tidak ada di database.
        
        Args:
            db: Database session
            
        Returns:
            Dictionary dengan hasil operasi
        """
        
        logger.info("Cleaning up orphaned FFmpeg processes")
        
        # Get all FFmpeg processes
        ffmpeg_processes = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if 'ffmpeg' in proc.info['name'].lower():
                    ffmpeg_processes.append(proc.info['pid'])
            except:
                pass
        
        # Get all PIDs from database
        db_pids = set()
        sessions = db.query(LiveSession).filter(
            LiveSession.ffmpeg_pid.isnot(None),
            LiveSession.status == 'running'
        ).all()
        
        for session in sessions:
            db_pids.add(session.ffmpeg_pid)
        
        # Find orphaned processes
        orphaned_pids = [pid for pid in ffmpeg_processes if pid not in db_pids]
        
        if not orphaned_pids:
            logger.info("No orphaned processes found")
            return {
                'success': True,
                'message': 'No orphaned processes',
                'killed_count': 0
            }
        
        # Kill orphaned processes
        killed_count = 0
        for pid in orphaned_pids:
            if self._kill_ffmpeg_process(pid, force=True):
                killed_count += 1
                logger.info(f"Killed orphaned process {pid}")
        
        logger.info(f"[OK] Killed {killed_count} orphaned processes")
        
        return {
            'success': True,
            'killed_count': killed_count,
            'orphaned_pids': orphaned_pids
        }


# Global instance
stream_control = StreamControlService()


# Background task for health monitoring
async def health_monitor_loop():
    """
    Background loop to check stream health and auto-restart failed streams.
    """
    import asyncio
    from app.database import SessionLocal
    from app.services.playlist_service import PlaylistService
    from app.models.video import Video
    from app.models.playlist import Playlist
    
    logger.info("Health monitor loop started")
    
    # Backoff configuration (seconds)
    backoff_delays = [5, 30, 120, 300, 600]
    
    while True:
        try:
            db = SessionLocal()
            
            # Check for dead processes in ffmpeg_service
            # This handles cleanup of the in-memory registry
            ffmpeg_service.cleanup_dead_processes()
            
            # Find sessions that should be running but aren't in active_processes
            # or sessions that have status='running' but the process is actually dead
            active_sessions = db.query(LiveSession).filter(
                LiveSession.status == 'running'
            ).all()
            
            for session in active_sessions:
                # Check for duration limit
                if session.max_duration_hours and session.max_duration_hours > 0:
                    current_duration_hours = session.get_duration_seconds() / 3600
                    if current_duration_hours >= session.max_duration_hours:
                        logger.info(f"Session {session.id} reached max duration ({session.max_duration_hours}h). Stopping.")
                        stream_control.stop_stream_by_session_id(db, session.id)
                        continue

                is_running = ffmpeg_service.is_process_running(session.id)
                
                if not is_running:
                    # Stream should be running but is not
                    logger.warning(f"Session {session.id} found dead. Attempting recovery...")
                    
                    # Capture last error
                    last_error = ffmpeg_service.get_last_error(session.id)
                    session.last_error = last_error
                    
                    if session.restart_count < len(backoff_delays):
                        # Calculate delay
                        delay = backoff_delays[session.restart_count]
                        logger.info(f"Recovery for session {session.id} in {delay}s (Attempt {session.restart_count + 1})")
                        
                        # We'll schedule the restart after a sleep
                        # For now, we update the DB state
                        session.status = 'recovering'
                        db.commit()
                        
                        # Run restart in background after delay
                        asyncio.create_task(
                            delayed_restart(session.id, delay)
                        )
                    else:
                        # Max retries reached
                        logger.error(f"Max retries reached for session {session.id}. Marking as failed.")
                        session.status = 'failed'
                        session.end_time = datetime.utcnow()
                        db.commit()
            
            db.close()
        except Exception as e:
            logger.error(f"Error in health monitor loop: {e}")
            
        await asyncio.sleep(10)  # Check every 10 seconds

async def delayed_restart(session_id: int, delay: int):
    """
    Helper function to perform a delayed restart.
    """
    import asyncio
    from app.database import SessionLocal
    from app.services.playlist_service import PlaylistService
    from app.models.video import Video
    from app.models.playlist import Playlist
    
    await asyncio.sleep(delay)
    
    db = SessionLocal()
    try:
        session = db.query(LiveSession).filter(LiveSession.id == session_id).first()
        if not session or session.status != 'recovering':
            return
            
        logger.info(f"Executing restart for session {session_id}")
        
        # Get stream key
        stream_key = db.query(StreamKey).filter(StreamKey.id == session.stream_key_id).first()
        if not stream_key or not stream_key.is_active:
            raise Exception("Stream key missing or inactive")
            
        # Get video paths
        video_paths = []
        if session.mode == 'single':
            video = db.query(Video).filter(Video.id == session.video_id).first()
            if not video: raise Exception("Video not found")
            video_paths = [video.path]
        else:
            playlist = db.query(Playlist).filter(Playlist.id == session.playlist_id).first()
            if not playlist: raise Exception("Playlist not found")
            playlist_service = PlaylistService(db)
            video_paths = playlist_service.get_video_paths(
                session.playlist_id, 
                shuffle=(playlist.mode == 'random')
            )
            
        if not video_paths:
            raise Exception("No videos found for restart")
            
        # Start FFmpeg
        process = ffmpeg_service.start_stream(
            session_id=session.id,
            video_paths=video_paths,
            stream_key=stream_key.get_full_key(),
            loop=True, # Assuming loop for 24/7 recovery
            mode=session.mode
        )
        
        if process:
            session.ffmpeg_pid = process.pid
            session.status = 'running'
            session.restart_count += 1
            session.last_error = None # Clear error on success
            db.commit()
            logger.info(f"[OK] Session {session_id} successfully restarted (PID: {process.pid})")
        else:
            raise Exception("FFmpeg failed to start during recovery")
            
    except Exception as e:
        logger.error(f"Failed to restart session {session_id}: {e}")
        if session:
            session.status = 'failed'
            session.last_error = f"Restart failed: {str(e)}"
            db.commit()
    finally:
        db.close()
