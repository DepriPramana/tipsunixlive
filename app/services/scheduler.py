"""
Scheduler service untuk menjadwalkan live streaming.
Mendukung single video dan playlist dengan LiveHistory tracking dan YouTube API integration.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from typing import List, Optional
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

logger.info("✅ Scheduler started")


def _execute_scheduled_stream(
    video_paths: List[str],
    playlist_id: Optional[int] = None,
    video_id: Optional[int] = None,
    title: str = "Scheduled Live Stream",
    description: str = "",
    use_youtube_api: bool = True,
    max_duration_hours: int = 0
):
    """
    Execute scheduled stream dengan LiveHistory tracking dan YouTube API.
    
    Args:
        video_paths: List path video
        playlist_id: ID playlist (optional)
        video_id: ID video (optional)
        title: Broadcast title
        description: Broadcast description
        use_youtube_api: Use YouTube API untuk auto-create broadcast
    """
    from app.services.stream_service import stream_service
    from app.services.live_history_service import LiveHistoryService
    from app.services.youtube_api_service import youtube_api
    from app.services.youtube_broadcast_service import YouTubeBroadcastService
    from app.database import SessionLocal
    
    logger.info("="*60)
    logger.info(f"🎬 Executing scheduled stream: {title}")
    logger.info("="*60)
    logger.info(f"Playlist ID: {playlist_id}, Video ID: {video_id}")
    logger.info(f"Use YouTube API: {use_youtube_api}")
    
    db = SessionLocal()
    stream_key = None
    broadcast_id = None
    
    try:
        # Step 1: Create YouTube broadcast if enabled
        if use_youtube_api:
            logger.info("📺 Creating YouTube broadcast...")
            
            # Authenticate
            if not youtube_api.youtube:
                youtube_api.authenticate()
            
            # Create complete setup
            youtube_result = youtube_api.create_complete_live_setup(
                title=title,
                description=description,
                scheduled_start_time=datetime.utcnow(),
                privacy_status="public",
                resolution="1080p",
                frame_rate="30fps"
            )
            
            if youtube_result:
                stream_key = youtube_result['stream_key']
                broadcast_id = youtube_result['broadcast_id']
                
                # Save to database
                broadcast_service = YouTubeBroadcastService(db)
                broadcast_record = broadcast_service.create_broadcast(
                    broadcast_id=youtube_result['broadcast_id'],
                    stream_id=youtube_result['stream_id'],
                    stream_key=youtube_result['stream_key'],
                    rtmp_url=youtube_result['rtmp_url'],
                    ingestion_address=youtube_result['ingestion_address'],
                    title=youtube_result['broadcast_title'],
                    description=description,
                    broadcast_url=youtube_result['broadcast_url'],
                    scheduled_start_time=datetime.utcnow()
                )
                
                logger.info(f"✅ YouTube broadcast created and saved to DB")
                logger.info(f"   Broadcast URL: {youtube_result['broadcast_url']}")
            else:
                logger.error("❌ Failed to create YouTube broadcast")
                use_youtube_api = False
        
        # Step 2: Create LiveHistory session
        history_service = LiveHistoryService(db)
        mode = 'playlist' if playlist_id else 'single'
        
        session = history_service.create_session(
            mode=mode,
            playlist_id=playlist_id,
            video_id=video_id,
            stream_key=stream_key,  # Save stream key to session
            max_duration_hours=max_duration_hours
        )
        
        logger.info(f"✅ LiveHistory session created: {session.id}")
        
        # Link broadcast to live history
        if use_youtube_api and broadcast_id:
            broadcast_service = YouTubeBroadcastService(db)
            broadcast_service.link_to_live_history(broadcast_id, session.id)
        
        # Step 3: Start stream
        success = stream_service.start_stream(
            video_paths=video_paths,
            playlist_id=playlist_id,
            video_id=video_id,
            loop=True,
            session_id=session.id,
            stream_key=stream_key  # Use YouTube stream key
        )
        
        if not success:
            # Update session as failed
            history_service.end_session(
                session_id=session.id,
                status='failed',
                error_message='Failed to start scheduled stream'
            )
            
            # Update broadcast status
            if use_youtube_api and broadcast_id:
                broadcast_service = YouTubeBroadcastService(db)
                broadcast_service.update_status(broadcast_id, 'error')
            
            logger.error("❌ Failed to start scheduled stream")
        else:
            logger.info("✅ Scheduled stream started successfully")
            
            # Update broadcast status to live
            if use_youtube_api and broadcast_id:
                broadcast_service = YouTubeBroadcastService(db)
                broadcast_service.update_status(
                    broadcast_id,
                    'live',
                    actual_start_time=datetime.utcnow()
                )
            
    except Exception as e:
        logger.error(f"❌ Error executing scheduled stream: {e}")
        
        # Update broadcast status to error
        if use_youtube_api and broadcast_id:
            try:
                broadcast_service = YouTubeBroadcastService(db)
                broadcast_service.update_status(broadcast_id, 'error')
            except:
                pass
    finally:
        db.close()


def schedule_live(
    run_time: datetime,
    video_paths: List[str],
    playlist_id: Optional[int] = None,
    video_id: Optional[int] = None,
    title: str = "Scheduled Live Stream",
    description: str = "",
    use_youtube_api: bool = True,
    max_duration_hours: int = 0
):
    """
    Menjadwalkan live streaming dengan YouTube API integration.
    
    Args:
        run_time: Waktu untuk menjalankan stream (datetime)
        video_paths: List path video untuk di-stream
        playlist_id: ID playlist (untuk mode playlist)
        video_id: ID video (untuk mode single)
        title: Broadcast title
        description: Broadcast description
        use_youtube_api: Use YouTube API untuk auto-create broadcast
    """
    logger.info("="*60)
    logger.info(f"📅 Scheduling live stream for {run_time}")
    logger.info("="*60)
    logger.info(f"Title: {title}")
    logger.info(f"Mode: {'playlist' if playlist_id else 'single'}")
    logger.info(f"Videos: {len(video_paths)}")
    logger.info(f"Use YouTube API: {use_youtube_api}")
    
    scheduler.add_job(
        _execute_scheduled_stream,
        'date',
        run_date=run_time,
        args=[video_paths],
        kwargs={
            'playlist_id': playlist_id,
            'video_id': video_id,
            'title': title,
            'description': description,
            'use_youtube_api': use_youtube_api,
            'max_duration_hours': max_duration_hours
        }
    )
    
    logger.info("✅ Live stream scheduled successfully")
    logger.info("="*60)


def get_scheduled_jobs():
    """
    Mendapatkan list scheduled jobs.
    
    Returns:
        List of scheduled jobs
    """
    jobs = scheduler.get_jobs()
    
    result = []
    for job in jobs:
        result.append({
            'id': job.id,
            'name': job.name,
            'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger': str(job.trigger)
        })
    
    return result


def cancel_scheduled_job(job_id: str) -> bool:
    """
    Cancel scheduled job by ID.
    
    Args:
        job_id: ID job yang akan dicancel
        
    Returns:
        True jika berhasil, False jika job tidak ditemukan
    """
    try:
        scheduler.remove_job(job_id)
        logger.info(f"✅ Job {job_id} cancelled")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to cancel job {job_id}: {e}")
        return False


