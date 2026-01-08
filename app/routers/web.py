"""
Router untuk web admin dashboard.
"""
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.services.video_service import VideoService
from app.services.playlist_service import PlaylistService
from app.services.live_history_service import LiveHistoryService
from app.services.stream_service import stream_service

router = APIRouter(prefix="/admin", tags=["Web Admin"])

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")


# Dependency untuk database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Dashboard utama"""
    from app.models.stream_key import StreamKey
    from app.models.live_session import LiveSession
    
    # Get statistics from legacy service
    history_service = LiveHistoryService(db)
    legacy_stats = history_service.get_statistics()
    
    # Get statistics from new LiveSession model
    total_new_sessions = db.query(LiveSession).count()
    failed_new_sessions = db.query(LiveSession).filter(LiveSession.status == 'failed').count()
    success_new_sessions = db.query(LiveSession).filter(LiveSession.status == 'stopped').count() # we count stopped as success for now
    
    # Combine stats
    stats = {
        "total_sessions": legacy_stats["total_sessions"] + total_new_sessions,
        "success_sessions": legacy_stats["success_sessions"] + success_new_sessions,
        "failed_sessions": legacy_stats["failed_sessions"] + failed_new_sessions,
        "active_sessions": db.query(LiveSession).filter(LiveSession.status == 'running').count(),
        "success_rate": 0
    }
    
    if stats["total_sessions"] > 0:
        stats["success_rate"] = (stats["success_sessions"] / stats["total_sessions"]) * 100
        
    # Get active sessions list for status synthesis
    active_sessions_list = db.query(LiveSession).filter(
        LiveSession.status == 'running'
    ).all()
    active_sessions_count = len(active_sessions_list)
    
    # Synthesize stream status for legacy template compatibility
    if active_sessions_count > 0:
        first = active_sessions_list[0]
        stream_status = {
            "is_streaming": True,
            "mode": first.mode,
            "playlist_id": first.playlist_id,
            "video_id": first.video_id,
            "session_id": first.id,
            "stream_key_name": first.stream_key.name if first.stream_key else "Default"
        }
    else:
        stream_status = stream_service.get_status()
    
    # Get total/active stream keys
    total_stream_keys = db.query(StreamKey).count()
    active_stream_keys = db.query(StreamKey).filter(StreamKey.is_active == True).count()
    
    # Get recent history
    recent_history = history_service.get_all_sessions(limit=5)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "stats": stats,
        "stream_status": stream_status,
        "recent_history": recent_history,
        "active_sessions": active_sessions_count,
        "total_stream_keys": total_stream_keys,
        "active_stream_keys": active_stream_keys
    })


@router.get("/videos", response_class=HTMLResponse)
async def videos_page(request: Request, db: Session = Depends(get_db)):
    """Halaman video list"""
    video_service = VideoService(db)
    videos = video_service.get_all_videos(limit=100)
    
    # Convert to dict for JSON serialization in template
    videos_dict = [v.to_dict() for v in videos]
    
    return templates.TemplateResponse("videos.html", {
        "request": request,
        "videos": videos_dict
    })


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Halaman upload video"""
    return templates.TemplateResponse("upload.html", {
        "request": request
    })


@router.get("/download", response_class=HTMLResponse)
async def download_page(request: Request):
    """Halaman download dari Google Drive"""
    return templates.TemplateResponse("download.html", {
        "request": request
    })


@router.get("/playlists", response_class=HTMLResponse)
async def playlists_page(request: Request, db: Session = Depends(get_db)):
    """Halaman playlist management"""
    playlist_service = PlaylistService(db)
    playlists = playlist_service.get_all_playlists()
    
    video_service = VideoService(db)
    videos = video_service.get_all_videos(limit=100)
    
    return templates.TemplateResponse("playlists.html", {
        "request": request,
        "playlists": playlists,
        "videos": videos
    })


@router.get("/live", response_class=HTMLResponse)
async def live_page(request: Request, db: Session = Depends(get_db)):
    """Halaman live streaming control"""
    from app.models.stream_key import StreamKey
    from app.models.live_session import LiveSession
    
    # Get playlists
    playlist_service = PlaylistService(db)
    playlists = playlist_service.get_all_playlists()
    
    # Get all videos for manual selection
    video_service = VideoService(db)
    videos = video_service.get_all_videos(limit=200)
    videos_dict = [v.to_dict() for v in videos]
    
    # Get stream keys (NEW)
    stream_keys = db.query(StreamKey).filter(
        StreamKey.is_active == True
    ).all()
    
    # Get active sessions (NEW)
    active_sessions = db.query(LiveSession).filter(
        LiveSession.status == 'running'
    ).all()
    
    # Legacy stream status for compatibility
    if active_sessions:
        first = active_sessions[0]
        stream_status = {
            "is_streaming": True,
            "mode": first.mode,
            "playlist_id": first.playlist_id,
            "video_id": first.video_id,
            "session_id": first.id,
            "stream_key_name": first.stream_key.name if first.stream_key else "Default"
        }
    else:
        stream_status = stream_service.get_status()
    
    return templates.TemplateResponse("live.html", {
        "request": request,
        "playlists": playlists,
        "videos": videos_dict,
        "stream_keys": stream_keys,  # NEW
        "active_sessions": active_sessions,  # NEW
        "stream_status": stream_status  # Legacy
    })


# REMOVED: /admin/schedule - Use Scheduled Live in /admin/live instead
# @router.get("/schedule", response_class=HTMLResponse)
# async def schedule_page(request: Request, db: Session = Depends(get_db)):
#     """Halaman scheduled live"""
#     ...


@router.get("/history", response_class=HTMLResponse)
async def history_page(request: Request, db: Session = Depends(get_db)):
    """Halaman live history"""
    from app.models.stream_key import StreamKey
    
    history_service = LiveHistoryService(db)
    history = history_service.get_all_sessions(limit=50)
    
    stream_keys = db.query(StreamKey).filter(StreamKey.is_active == True).all()
    
    return templates.TemplateResponse("history.html", {
        "request": request,
        "history": history,
        "stream_keys": stream_keys
    })


@router.get("/calendar", response_class=HTMLResponse)
async def calendar_page(request: Request, db: Session = Depends(get_db)):
    """Halaman calendar view untuk jadwal siaran"""
    return templates.TemplateResponse("calendar.html", {
        "request": request
    })

