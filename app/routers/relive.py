"""
Re-Live router untuk mengulang live streaming dari history.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models.live_history import LiveHistory
from app.models.stream_key import StreamKey
from app.services.ffmpeg_service import ffmpeg_service
from app.services.live_scheduler_service import live_scheduler
from app.models.live_session import LiveSession

router = APIRouter(prefix="/relive", tags=["Re-Live"])


def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ReLiveRequest(BaseModel):
    """Request model untuk re-live"""
    history_id: int
    stream_key_id: int
    stream_title: Optional[str] = None
    loop: bool = True


class ReLiveScheduleRequest(BaseModel):
    """Request model untuk scheduled re-live"""
    history_id: int
    stream_key_id: int
    scheduled_time: str  # ISO format
    stream_title: Optional[str] = None
    loop: bool = True
    max_duration_hours: Optional[int] = 0


@router.post("/start")
def start_relive(
    request: ReLiveRequest,
    db: Session = Depends(get_db)
):
    """
    Start re-live immediately.
    Mengulang live dari history dengan stream key baru.
    
    Args:
        request: ReLiveRequest
        db: Database session
        
    Returns:
        Live session info
    """
    
    # Get history
    history = db.query(LiveHistory).filter(
        LiveHistory.id == request.history_id
    ).first()
    
    if not history:
        raise HTTPException(404, f"History {request.history_id} not found")
    
    # Validate stream key
    stream_key = db.query(StreamKey).filter(
        StreamKey.id == request.stream_key_id
    ).first()
    
    if not stream_key:
        raise HTTPException(404, f"Stream key {request.stream_key_id} not found")
    
    if not stream_key.is_active:
        raise HTTPException(400, f"Stream key '{stream_key.name}' is not active")
    
    # Check if stream key is already in use
    existing_session = db.query(LiveSession).filter(
        LiveSession.stream_key_id == request.stream_key_id,
        LiveSession.status == 'running'
    ).first()
    
    if existing_session:
        raise HTTPException(
            409,
            f"Stream key '{stream_key.name}' is already in use by session {existing_session.id}"
        )
    
    # Check concurrent limit
    from app.config import MAX_CONCURRENT_STREAMS
    
    total_active = db.query(LiveSession).filter(
        LiveSession.status == 'running'
    ).count()
    
    if total_active >= MAX_CONCURRENT_STREAMS:
        raise HTTPException(
            429,
            f"Maximum concurrent streams limit reached ({MAX_CONCURRENT_STREAMS})"
        )
    
    # Get video paths from history
    video_paths = []
    
    if history.mode == 'single':
        if not history.video:
            raise HTTPException(400, f"History video not found")
        video_paths = [history.video.path]
        
    else:  # playlist mode
        if not history.playlist:
            raise HTTPException(400, f"History playlist not found")
        
        from app.services.playlist_service import PlaylistService
        playlist_service = PlaylistService(db)
        video_paths = playlist_service.get_video_paths(
            history.playlist_id,
            shuffle=(history.playlist.mode == 'random')
        )
        
        if not video_paths:
            raise HTTPException(400, f"Playlist has no videos")
    
    # Create new live session
    session = LiveSession(
        stream_key_id=request.stream_key_id,
        video_id=history.video_id,
        playlist_id=history.playlist_id,
        mode=history.mode,
        status='starting',
        max_duration_hours=request.max_duration_hours
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    
    # Start FFmpeg
    try:
        process = ffmpeg_service.start_stream(
            session_id=session.id,
            video_paths=video_paths,
            stream_key=stream_key.get_full_key(),
            loop=request.loop,
            mode=history.mode
        )
        
        if not process:
            session.status = 'failed'
            db.commit()
            raise HTTPException(500, "Failed to start FFmpeg process")
        
        # Update session
        session.ffmpeg_pid = process.pid
        session.status = 'running'
        db.commit()
        
        # Create new history entry
        new_history = LiveHistory(
            stream_key_id=request.stream_key_id,
            video_id=history.video_id,
            playlist_id=history.playlist_id,
            mode=history.mode,
            stream_title=request.stream_title or f"Re-Live: {history.stream_title or 'Untitled'}",
            ffmpeg_pid=process.pid,
            status='running',
            stream_key=stream_key._mask_key(),
            max_duration_hours=request.max_duration_hours
        )
        
        db.add(new_history)
        db.commit()
        db.refresh(new_history)
        
        return {
            "success": True,
            "session_id": session.id,
            "history_id": new_history.id,
            "stream_key_name": stream_key.name,
            "mode": history.mode,
            "ffmpeg_pid": process.pid,
            "status": "running",
            "message": f"Re-live started from history {request.history_id}"
        }
        
    except Exception as e:
        session.status = 'failed'
        db.commit()
        raise HTTPException(500, f"Error starting re-live: {str(e)}")


@router.post("/schedule")
def schedule_relive(
    request: ReLiveScheduleRequest,
    db: Session = Depends(get_db)
):
    """
    Schedule re-live for later.
    Jadwalkan ulang live dari history dengan stream key baru.
    
    Args:
        request: ReLiveScheduleRequest
        db: Database session
        
    Returns:
        Scheduled live info
    """
    
    # Get history
    history = db.query(LiveHistory).filter(
        LiveHistory.id == request.history_id
    ).first()
    
    if not history:
        raise HTTPException(404, f"History {request.history_id} not found")
    
    # Parse scheduled time
    try:
        scheduled_time = datetime.fromisoformat(request.scheduled_time)
    except ValueError:
        raise HTTPException(400, "Invalid datetime format. Use ISO format")
    
    if scheduled_time <= datetime.now():
        raise HTTPException(400, "Scheduled time must be in the future")
    
    # Validate stream key
    stream_key = db.query(StreamKey).filter(
        StreamKey.id == request.stream_key_id
    ).first()
    
    if not stream_key:
        raise HTTPException(404, f"Stream key {request.stream_key_id} not found")
    
    if not stream_key.is_active:
        raise HTTPException(400, f"Stream key '{stream_key.name}' is not active")
    
    # Schedule the live
    try:
        scheduled_live = live_scheduler.schedule_live(
            db=db,
            stream_key_id=request.stream_key_id,
            scheduled_time=scheduled_time,
            video_id=history.video_id,
            playlist_id=history.playlist_id,
            mode=history.mode,
            loop=request.loop,
            max_duration_hours=request.max_duration_hours
        )
        
        return {
            "success": True,
            "schedule_id": scheduled_live.id,
            "history_id": request.history_id,
            "stream_key_name": stream_key.name,
            "scheduled_time": scheduled_time.isoformat(),
            "mode": history.mode,
            "job_id": scheduled_live.job_id,
            "message": f"Re-live scheduled from history {request.history_id}"
        }
        
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Error scheduling re-live: {str(e)}")


@router.get("/history/{history_id}")
def get_history_details(history_id: int, db: Session = Depends(get_db)):
    """
    Get history details for re-live.
    
    Args:
        history_id: LiveHistory ID
        db: Database session
        
    Returns:
        History details
    """
    
    history = db.query(LiveHistory).filter(
        LiveHistory.id == history_id
    ).first()
    
    if not history:
        raise HTTPException(404, f"History {history_id} not found")
    
    return history.to_dict()


@router.get("/available-histories")
def get_available_histories(
    limit: int = 50,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get available histories for re-live.
    
    Args:
        limit: Maximum number of results
        status: Filter by status (success, stopped, failed)
        db: Database session
        
    Returns:
        List of histories
    """
    
    query = db.query(LiveHistory)
    
    if status:
        query = query.filter(LiveHistory.status == status)
    
    histories = query.order_by(
        LiveHistory.start_time.desc()
    ).limit(limit).all()
    
    return [h.to_dict() for h in histories]


@router.get("/available-stream-keys")
def get_available_stream_keys(db: Session = Depends(get_db)):
    """
    Get available stream keys for re-live.
    Only returns active keys that are not currently in use.
    
    Args:
        db: Database session
        
    Returns:
        List of available stream keys
    """
    
    # Get all active stream keys
    active_keys = db.query(StreamKey).filter(
        StreamKey.is_active == True
    ).all()
    
    # Get currently used stream keys
    used_key_ids = set()
    active_sessions = db.query(LiveSession).filter(
        LiveSession.status == 'running'
    ).all()
    
    for session in active_sessions:
        used_key_ids.add(session.stream_key_id)
    
    # Filter available keys
    available_keys = [
        {
            'id': key.id,
            'name': key.name,
            'is_available': key.id not in used_key_ids
        }
        for key in active_keys
    ]
    
    return available_keys
