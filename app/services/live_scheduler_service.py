"""
Live Streaming Scheduler Service menggunakan APScheduler.
Mendukung multiple concurrent scheduled jobs.
"""
import logging
from datetime import datetime
from typing import Optional, Dict, List
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.scheduled_live import ScheduledLive
from app.models.live_session import LiveSession
from app.models.stream_key import StreamKey
from app.models.video import Video
from app.models.playlist import Playlist
from app.services.ffmpeg_service import ffmpeg_service
from app.services.playlist_service import PlaylistService

logger = logging.getLogger(__name__)


class LiveSchedulerService:
    """Service untuk scheduling live streaming"""
    
    def __init__(self):
        # Initialize APScheduler
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        logger.info("Live Scheduler started")
    
    def schedule_live(
        self,
        db: Session,
        stream_key_id: int,
        scheduled_time: datetime,
        video_id: Optional[int] = None,
        playlist_id: Optional[int] = None,
        mode: str = 'playlist',
        loop: bool = True,
        recurrence: str = 'none',
        max_duration_hours: int = 0
    ) -> ScheduledLive:
        """
        Schedule live streaming.
        
        Args:
            db: Database session
            stream_key_id: StreamKey ID
            scheduled_time: When to start streaming
            video_id: Video ID (for single mode)
            playlist_id: Playlist ID (for playlist mode)
            mode: 'single' or 'playlist'
            loop: Enable loop
            
        Returns:
            ScheduledLive object
        """
        
        # Validate stream key
        stream_key = db.query(StreamKey).filter(
            StreamKey.id == stream_key_id
        ).first()
        
        if not stream_key:
            raise ValueError(f"Stream key {stream_key_id} not found")
        
        if not stream_key.is_active:
            raise ValueError(f"Stream key '{stream_key.name}' is not active")
        
        # Validate video/playlist
        if mode == 'single' and not video_id:
            raise ValueError("video_id required for single mode")
        
        if mode == 'playlist' and not playlist_id:
            raise ValueError("playlist_id required for playlist mode")
        
        # Create scheduled live record
        scheduled_live = ScheduledLive(
            stream_key_id=stream_key_id,
            video_id=video_id,
            playlist_id=playlist_id,
            scheduled_time=scheduled_time,
            mode=mode,
            loop=loop,
            recurrence=recurrence,
            max_duration_hours=max_duration_hours,
            status='pending'
        )
        
        db.add(scheduled_live)
        db.commit()
        db.refresh(scheduled_live)
        
        # Generate job ID
        job_id = f"live_schedule_{scheduled_live.id}"
        scheduled_live.job_id = job_id
        db.commit()
        
        # Schedule job with APScheduler
        self.scheduler.add_job(
            func=self._execute_scheduled_live,
            trigger=DateTrigger(run_date=scheduled_time),
            id=job_id,
            args=[scheduled_live.id],
            replace_existing=True
        )
        
        logger.info(f"Scheduled live {scheduled_live.id} for {scheduled_time}")
        logger.info(f"  Stream Key: {stream_key.name}")
        logger.info(f"  Mode: {mode}")
        logger.info(f"  Job ID: {job_id}")
        
        return scheduled_live
    
    def _execute_scheduled_live(self, scheduled_live_id: int):
        """
        Execute scheduled live streaming.
        Called by APScheduler at scheduled time.
        
        Args:
            scheduled_live_id: ScheduledLive ID
        """
        
        db = SessionLocal()
        
        try:
            # Get scheduled live
            scheduled_live = db.query(ScheduledLive).filter(
                ScheduledLive.id == scheduled_live_id
            ).first()
            
            if not scheduled_live:
                logger.error(f"Scheduled live {scheduled_live_id} not found")
                return
            
            logger.info(f"Executing scheduled live {scheduled_live_id}")
            
            # Update status
            scheduled_live.status = 'running'
            scheduled_live.started_at = datetime.utcnow()
            db.commit()
            
            # Get stream key
            stream_key = db.query(StreamKey).filter(
                StreamKey.id == scheduled_live.stream_key_id
            ).first()
            
            if not stream_key:
                raise Exception(f"Stream key {scheduled_live.stream_key_id} not found")
            
            if not stream_key.is_active:
                raise Exception(f"Stream key '{stream_key.name}' is not active")
            
            # COLLISION DETECTION 1: Check if stream key is already in use
            existing_session = db.query(LiveSession).filter(
                LiveSession.stream_key_id == scheduled_live.stream_key_id,
                LiveSession.status == 'running'
            ).first()
            
            if existing_session:
                error_msg = (
                    f"Stream key '{stream_key.name}' (ID: {stream_key.id}) is already in use "
                    f"by live session {existing_session.id}. "
                    f"Scheduled live {scheduled_live_id} skipped."
                )
                logger.warning(error_msg)
                raise Exception(error_msg)
            
            # COLLISION DETECTION 2: Check concurrent streams limit
            from app.config import MAX_CONCURRENT_STREAMS
            
            total_active = db.query(LiveSession).filter(
                LiveSession.status == 'running'
            ).count()
            
            if total_active >= MAX_CONCURRENT_STREAMS:
                error_msg = (
                    f"Maximum concurrent streams limit reached ({MAX_CONCURRENT_STREAMS}). "
                    f"Scheduled live {scheduled_live_id} skipped."
                )
                logger.warning(error_msg)
                raise Exception(error_msg)
            
            # Get video paths
            video_paths = []
            
            if scheduled_live.mode == 'single':
                video = db.query(Video).filter(
                    Video.id == scheduled_live.video_id
                ).first()
                
                if not video:
                    raise Exception(f"Video {scheduled_live.video_id} not found")
                
                video_paths = [video.path]
                
                # NOTE: Video can be used by multiple streams (different keys)
                # This is allowed - no collision check needed for video
                logger.info(f"Using video: {video.name}")
                
            else:  # playlist mode
                playlist = db.query(Playlist).filter(
                    Playlist.id == scheduled_live.playlist_id
                ).first()
                
                if not playlist:
                    raise Exception(f"Playlist {scheduled_live.playlist_id} not found")
                
                playlist_service = PlaylistService(db)
                video_paths = playlist_service.get_video_paths(
                    scheduled_live.playlist_id,
                    shuffle=(playlist.mode == 'random')
                )
                
                if not video_paths:
                    raise Exception(f"Playlist {scheduled_live.playlist_id} has no videos")
                
                # NOTE: Playlist can be used by multiple streams (different keys)
                # This is allowed - no collision check needed for playlist
                logger.info(f"Using playlist: {playlist.name} ({len(video_paths)} videos)")
            
            # Create live session
            live_session = LiveSession(
                stream_key_id=scheduled_live.stream_key_id,
                video_id=scheduled_live.video_id,
                playlist_id=scheduled_live.playlist_id,
                mode=scheduled_live.mode,
                status='starting',
                max_duration_hours=scheduled_live.max_duration_hours,
                start_time=datetime.utcnow()
            )
            
            db.add(live_session)
            db.commit()
            db.refresh(live_session)
            
            logger.info(f"Created live session {live_session.id}")
            
            # Start FFmpeg
            process = ffmpeg_service.start_stream(
                session_id=live_session.id,
                video_paths=video_paths,
                stream_key=stream_key.get_full_key(),
                loop=scheduled_live.loop,
                mode=scheduled_live.mode
            )
            
            if not process:
                raise Exception("Failed to start FFmpeg process")
            
            # Update live session
            live_session.ffmpeg_pid = process.pid
            live_session.status = 'running'
            db.commit()
            
            # Update scheduled live
            scheduled_live.live_session_id = live_session.id
            scheduled_live.status = 'completed'
            scheduled_live.completed_at = datetime.utcnow()
            db.commit()
            
            # HANDLE RECURRENCE (NEW)
            if scheduled_live.recurrence and scheduled_live.recurrence != 'none':
                from datetime import timedelta
                
                next_time = None
                if scheduled_live.recurrence == 'daily':
                    next_time = scheduled_live.scheduled_time + timedelta(days=1)
                elif scheduled_live.recurrence == 'weekly':
                    next_time = scheduled_live.scheduled_time + timedelta(weeks=1)
                
                if next_time:
                    logger.info(f"Adding recurring job for {scheduled_live.recurrence} at {next_time}")
                    self.schedule_live(
                        db=db,
                        stream_key_id=scheduled_live.stream_key_id,
                        scheduled_time=next_time,
                        video_id=scheduled_live.video_id,
                        playlist_id=scheduled_live.playlist_id,
                        mode=scheduled_live.mode,
                        loop=scheduled_live.loop,
                        recurrence=scheduled_live.recurrence,
                        max_duration_hours=scheduled_live.max_duration_hours
                    )
            
            logger.info(f"[OK] Scheduled live {scheduled_live_id} executed successfully")
            logger.info(f"     Stream Key: {stream_key.name}")
            logger.info(f"     Live Session: {live_session.id}")
            logger.info(f"     FFmpeg PID: {process.pid}")
            logger.info(f"     Mode: {scheduled_live.mode}")
            logger.info(f"     Loop: {scheduled_live.loop}")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[FAILED] Scheduled live {scheduled_live_id} execution failed")
            logger.error(f"         Error: {error_msg}")
            
            # Update as failed
            if scheduled_live:
                scheduled_live.status = 'failed'
                scheduled_live.error_message = error_msg
                scheduled_live.completed_at = datetime.utcnow()
                db.commit()
                
                logger.error(f"         Scheduled live {scheduled_live_id} marked as failed in database")
        
        finally:
            db.close()
    
    def cancel_scheduled_live(self, db: Session, scheduled_live_id: int) -> bool:
        """
        Cancel scheduled live.
        
        Args:
            db: Database session
            scheduled_live_id: ScheduledLive ID
            
        Returns:
            True if cancelled successfully
        """
        
        scheduled_live = db.query(ScheduledLive).filter(
            ScheduledLive.id == scheduled_live_id
        ).first()
        
        if not scheduled_live:
            logger.error(f"Scheduled live {scheduled_live_id} not found")
            return False
        
        if scheduled_live.status not in ['pending', 'running']:
            logger.warning(f"Cannot cancel scheduled live {scheduled_live_id} with status {scheduled_live.status}")
            return False
        
        # Remove job from scheduler
        if scheduled_live.job_id:
            try:
                self.scheduler.remove_job(scheduled_live.job_id)
                logger.info(f"Removed job {scheduled_live.job_id} from scheduler")
            except Exception as e:
                logger.warning(f"Error removing job: {e}")
        
        # Update status
        scheduled_live.status = 'cancelled'
        scheduled_live.completed_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Cancelled scheduled live {scheduled_live_id}")
        return True
    
    def get_scheduled_lives(
        self,
        db: Session,
        status: Optional[str] = None,
        stream_key_id: Optional[int] = None
    ) -> List[ScheduledLive]:
        """
        Get scheduled lives.
        
        Args:
            db: Database session
            status: Filter by status
            stream_key_id: Filter by stream key
            
        Returns:
            List of ScheduledLive objects
        """
        
        query = db.query(ScheduledLive)
        
        if status:
            query = query.filter(ScheduledLive.status == status)
        
        if stream_key_id:
            query = query.filter(ScheduledLive.stream_key_id == stream_key_id)
        
        return query.order_by(ScheduledLive.scheduled_time.desc()).all()
    
    def get_pending_jobs(self, db: Session) -> List[ScheduledLive]:
        """Get all pending scheduled jobs"""
        return self.get_scheduled_lives(db, status='pending')
    
    def get_scheduler_jobs(self) -> List[Dict]:
        """Get all jobs from APScheduler"""
        jobs = []
        
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        
        return jobs
    
    def shutdown(self):
        """Shutdown scheduler"""
        self.scheduler.shutdown()
        logger.info("Live Scheduler shutdown")


# Global instance
live_scheduler = LiveSchedulerService()
