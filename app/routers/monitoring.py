"""
Monitoring dashboard endpoints.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import SessionLocal
from app.models.live_session import LiveSession
from app.models.stream_key import StreamKey
from app.services.stream_control_service import stream_control

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
templates = Jinja2Templates(directory="templates")


def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/monitoring", response_class=HTMLResponse)
def monitoring_dashboard(request: Request, db: Session = Depends(get_db)):
    """
    Live monitoring dashboard.
    Shows all active live streams with real-time updates.
    """
    
    # Get all active sessions
    active_sessions = db.query(LiveSession).filter(
        LiveSession.status == 'running'
    ).order_by(LiveSession.start_time.desc()).all()
    
    # Prepare session data
    sessions_data = []
    for session in active_sessions:
        # Calculate runtime
        runtime_seconds = (datetime.utcnow() - session.start_time).total_seconds()
        hours = int(runtime_seconds // 3600)
        minutes = int((runtime_seconds % 3600) // 60)
        seconds = int(runtime_seconds % 60)
        runtime = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # Get content info
        content_name = "N/A"
        content_type = "Unknown"
        
        if session.mode == 'single' and session.video:
            content_name = session.video.name
            content_type = "Video"
        elif session.mode == 'playlist' and session.playlist:
            content_name = session.playlist.name
            content_type = "Playlist"
        
        sessions_data.append({
            'id': session.id,
            'stream_key_id': session.stream_key_id,
            'stream_key_name': session.stream_key.name if session.stream_key else 'N/A',
            'content_type': content_type,
            'content_name': content_name,
            'mode': session.mode,
            'ffmpeg_pid': session.ffmpeg_pid,
            'start_time': session.start_time,
            'runtime': runtime,
            'runtime_seconds': int(runtime_seconds)
        })
    
    return templates.TemplateResponse("monitoring.html", {
        "request": request,
        "sessions": sessions_data,
        "total_active": len(sessions_data)
    })


@router.get("/monitoring/api/sessions")
def get_active_sessions_api(db: Session = Depends(get_db)):
    """
    API endpoint for real-time session updates.
    Returns JSON data for AJAX polling.
    """
    
    # Get all active sessions
    active_sessions = db.query(LiveSession).filter(
        LiveSession.status == 'running'
    ).order_by(LiveSession.start_time.desc()).all()
    
    # Prepare session data
    sessions_data = []
    for session in active_sessions:
        # Calculate runtime
        runtime_seconds = (datetime.utcnow() - session.start_time).total_seconds()
        hours = int(runtime_seconds // 3600)
        minutes = int((runtime_seconds % 3600) // 60)
        seconds = int(runtime_seconds % 60)
        runtime = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # Get content info
        content_name = "N/A"
        content_type = "Unknown"
        
        if session.mode == 'single' and session.video:
            content_name = session.video.name
            content_type = "Video"
        elif session.mode == 'playlist' and session.playlist:
            content_name = session.playlist.name
            content_type = "Playlist"
        
        sessions_data.append({
            'id': session.id,
            'stream_key_id': session.stream_key_id,
            'stream_key_name': session.stream_key.name if session.stream_key else 'N/A',
            'content_type': content_type,
            'content_name': content_name,
            'mode': session.mode,
            'ffmpeg_pid': session.ffmpeg_pid,
            'start_time': session.start_time.isoformat(),
            'runtime': runtime,
            'runtime_seconds': int(runtime_seconds)
        })
    
    return JSONResponse({
        'total_active': len(sessions_data),
        'sessions': sessions_data,
        'timestamp': datetime.utcnow().isoformat()
    })


@router.post("/monitoring/stop/{session_id}")
def stop_session_from_monitoring(session_id: int, db: Session = Depends(get_db)):
    """
    Stop live session from monitoring dashboard.
    """
    
    return JSONResponse(result)


@router.get("/api/system-stats")
def get_system_stats():
    """
    Get current server resource usage stats.
    """
    import psutil
    
    cpu_usage = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return JSONResponse({
        'cpu': {
            'percent': cpu_usage,
        },
        'memory': {
            'percent': memory.percent,
            'used_gb': round(memory.used / (1024**3), 2),
            'total_gb': round(memory.total / (1024**3), 2)
        },
        'disk': {
            'percent': disk.percent,
            'used_gb': round(disk.used / (1024**3), 2),
            'total_gb': round(disk.total / (1024**3), 2)
        }
    })

