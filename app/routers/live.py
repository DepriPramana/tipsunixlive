"""
Live streaming router untuk manual & scheduled streaming.
Mendukung multiple stream keys dan concurrent streams.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import SessionLocal
from app.models.stream_key import StreamKey
from app.models.video import Video
from app.models.playlist import Playlist
from app.models.live_session import LiveSession
from app.services.ffmpeg_service import ffmpeg_service
from app.services.stream_control_service import stream_control
from app.services.playlist_service import PlaylistService

router = APIRouter(prefix="/live", tags=["Live Streaming"])


def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ManualLiveRequest(BaseModel):
    """Request model untuk manual live streaming"""
    stream_key_id: int
    video_id: Optional[int] = None
    playlist_id: Optional[int] = None
    mode: str  # 'single' or 'playlist'
    loop: bool = True
    youtube_id: Optional[str] = None
    max_duration_hours: Optional[int] = 0  # 0 or null = unlimited


class ManualLiveResponse(BaseModel):
    """Response model untuk manual live streaming"""
    success: bool
    session_id: int
    stream_key_name: str
    mode: str
    ffmpeg_pid: int
    status: str
    message: str


@router.post("/manual", response_model=ManualLiveResponse)
def start_manual_live(
    request: ManualLiveRequest,
    db: Session = Depends(get_db)
):
    """
    Start manual live streaming.
    
    Args:
        request: ManualLiveRequest dengan stream_key_id dan video/playlist
        db: Database session
        
    Returns:
        ManualLiveResponse dengan session info
        
    Raises:
        HTTPException: Jika validasi gagal atau error
    """
    
    # Validate mode
    if request.mode not in ['single', 'playlist']:
        raise HTTPException(400, "Mode must be 'single' or 'playlist'")
    
    # Validate video_id or playlist_id
    if request.mode == 'single' and not request.video_id:
        raise HTTPException(400, "video_id required for single mode")
    
    if request.mode == 'playlist' and not request.playlist_id:
        raise HTTPException(400, "playlist_id required for playlist mode")
    
    # Step 1: Validate stream key
    stream_key = db.query(StreamKey).filter(
        StreamKey.id == request.stream_key_id
    ).first()
    
    if not stream_key:
        raise HTTPException(404, f"Stream key {request.stream_key_id} not found")
    
    if not stream_key.is_active:
        raise HTTPException(400, f"Stream key '{stream_key.name}' is not active")
    
    # Step 2: Get video paths
    video_paths = []
    
    if request.mode == 'single':
        # Get single video
        video = db.query(Video).filter(Video.id == request.video_id).first()
        
        if not video:
            raise HTTPException(404, f"Video {request.video_id} not found")
        
        video_paths = [video.path]
        
    else:  # playlist mode
        # Get playlist videos
        playlist = db.query(Playlist).filter(
            Playlist.id == request.playlist_id
        ).first()
        
        if not playlist:
            raise HTTPException(404, f"Playlist {request.playlist_id} not found")
        
        # Get video paths from playlist
        playlist_service = PlaylistService(db)
        video_paths = playlist_service.get_video_paths(
            request.playlist_id,
            shuffle=(playlist.mode == 'random')
        )
        
        if not video_paths:
            raise HTTPException(400, f"Playlist {request.playlist_id} has no videos")
    
    # Step 3: VALIDATIONS
    
    # Validation 1: Check if stream key is already in use
    existing_session = db.query(LiveSession).filter(
        LiveSession.stream_key_id == request.stream_key_id,
        LiveSession.status == 'running'
    ).first()
    
    if existing_session:
        raise HTTPException(
            409,  # Conflict
            f"Stream key '{stream_key.name}' is already in use by session {existing_session.id}. "
            f"Each stream key can only be used by one live stream at a time."
        )
    
    # Validation 2: Check total concurrent streams limit
    from app.config import MAX_CONCURRENT_STREAMS
    
    total_active = db.query(LiveSession).filter(
        LiveSession.status == 'running'
    ).count()
    
    if total_active >= MAX_CONCURRENT_STREAMS:
        raise HTTPException(
            429,  # Too Many Requests
            f"Maximum concurrent streams limit reached ({MAX_CONCURRENT_STREAMS}). "
            f"Please stop an existing stream before starting a new one."
        )
    
    # Validation 3: Check stream key max_concurrent (future feature)
    # This allows limiting concurrent streams per stream key if needed
    # Currently not enforced since we already check for duplicate usage above
    
    # Step 4: Create live session
    session = LiveSession(
        stream_key_id=request.stream_key_id,
        video_id=request.video_id,
        playlist_id=request.playlist_id,
        mode=request.mode,
        status='starting',
        youtube_id=request.youtube_id,
        max_duration_hours=request.max_duration_hours
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    
    # Step 4: Start FFmpeg process
    try:
        process = ffmpeg_service.start_stream(
            session_id=session.id,
            video_paths=video_paths,
            stream_key=stream_key.get_full_key(),
            loop=request.loop,
            mode=request.mode
        )
        
        if not process:
            # Failed to start
            session.status = 'failed'
            db.commit()
            raise HTTPException(500, "Failed to start FFmpeg process")
        
        # Update session with PID
        session.ffmpeg_pid = process.pid
        session.status = 'running'
        db.commit()
        db.refresh(session)
        
        # Return response
        return ManualLiveResponse(
            success=True,
            session_id=session.id,
            stream_key_name=stream_key.name,
            mode=request.mode,
            ffmpeg_pid=process.pid,
            status='running',
            message=f"Live streaming started successfully"
        )
        
    except Exception as e:
        # Update session as failed
        session.status = 'failed'
        db.commit()
        
        raise HTTPException(500, f"Error starting stream: {str(e)}")


@router.post("/stop/{session_id}")
def stop_live(session_id: int, db: Session = Depends(get_db)):
    """
    Stop live streaming session.
    
    Args:
        session_id: LiveSession ID
        db: Database session
        
    Returns:
        Result dictionary
    """
    
    result = stream_control.stop_stream_by_session_id(db, session_id)
    
    if not result['success']:
        raise HTTPException(500, result.get('error', 'Failed to stop stream'))
    
    return result


@router.get("/status/{session_id}")
def get_live_status(session_id: int, db: Session = Depends(get_db)):
    """
    Get live streaming session status.
    
    Args:
        session_id: LiveSession ID
        db: Database session
        
    Returns:
        Session status dictionary
    """
    
    # Get session from database
    session = db.query(LiveSession).filter(
        LiveSession.id == session_id
    ).first()
    
    if not session:
        raise HTTPException(404, f"Session {session_id} not found")
    
    # Get FFmpeg process status
    ffmpeg_status = ffmpeg_service.get_process_status(session_id)
    
    # Build response
    response = session.to_dict()
    
    if ffmpeg_status:
        response['ffmpeg_status'] = ffmpeg_status
    
    return response


@router.get("/active")
def get_active_sessions(db: Session = Depends(get_db)):
    """
    Get all active live sessions.
    
    Args:
        db: Database session
        
    Returns:
        List of active sessions
    """
    
    sessions = db.query(LiveSession).filter(
        LiveSession.status == 'running'
    ).all()
    
    return [session.to_dict() for session in sessions]


@router.post("/stop-all")
def stop_all_sessions(db: Session = Depends(get_db)):
    """
    Stop all active live sessions.
    
    Args:
        db: Database session
        
    Returns:
        Result dictionary
    """
    
    result = stream_control.stop_all_active_streams(db)
    return result


@router.get("/status")
def get_live_status(db: Session = Depends(get_db)):
    """
    Get overall live streaming status.
    
    Args:
        db: Database session
        
    Returns:
        Status dictionary with active sessions info
    """
    
    # Get active sessions
    active_sessions = db.query(LiveSession).filter(
        LiveSession.status == 'running'
    ).all()
    
    # Build response
    is_streaming = len(active_sessions) > 0
    
    response = {
        'is_streaming': is_streaming,
        'total_active': len(active_sessions),
        'sessions': []
    }
    
    if is_streaming:
        # Get first session for legacy compatibility
        first_session = active_sessions[0]
        response['mode'] = first_session.mode
        response['session_id'] = first_session.id
        response['stream_key_id'] = first_session.stream_key_id
        response['max_duration_hours'] = first_session.max_duration_hours
        
        if first_session.playlist_id:
            response['playlist_id'] = first_session.playlist_id
        
        # Add all sessions
        for session in active_sessions:
            response['sessions'].append({
                'id': session.id,
                'stream_key_id': session.stream_key_id,
                'stream_key_name': session.stream_key.name if session.stream_key else None,
                'mode': session.mode,
                'status': session.status,
                'ffmpeg_pid': session.ffmpeg_pid
            })
    
    return response


@router.post("/stop-by-key/{stream_key_id}")
def stop_by_stream_key(
    stream_key_id: int,
    stop_all: bool = True,
    db: Session = Depends(get_db)
):
    """
    Stop sessions by stream key ID.
    
    Args:
        stream_key_id: StreamKey ID
        stop_all: Stop all sessions with this key
        db: Database session
        
    Returns:
        Result dictionary
    """
    
    result = stream_control.stop_stream_by_stream_key_id(
        db,
        stream_key_id,
        stop_all=stop_all
    )
    
    if not result['success']:
        raise HTTPException(500, result.get('error', 'Failed to stop streams'))
    
    return result
