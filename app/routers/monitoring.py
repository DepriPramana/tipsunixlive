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
from app.services.ffmpeg_service import ffmpeg_service

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
            'max_duration_hours': session.max_duration_hours,
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
            'max_duration_hours': session.max_duration_hours,
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


@router.get("/monitoring/logs/{session_id}")
def get_session_logs(session_id: int, lines: int = 100):
    """
    Get FFmpeg logs for a specific session.
    
    Args:
        session_id: Live session ID
        lines: Number of lines to show from the end (tail)
    """
    import os
    
    log_content = ffmpeg_service.get_log_content(session_id, lines=lines)
    
    if not log_content:
        return JSONResponse({
            'success': False,
            'message': f'No logs found for session {session_id}'
        }, status_code=404)
    
    # Get more info about the session
    status = ffmpeg_service.get_process_status(session_id)
    
    return JSONResponse({
        'success': True,
        'session_id': session_id,
        'lines': lines,
        'log_content': log_content,
        'status': status
    })


@router.get("/monitoring/logs")
def list_all_logs():
    """
    List all available FFmpeg log files.
    """
    import os
    import glob
    from pathlib import Path
    
    log_dir = "logs/ffmpeg"
    if not os.path.exists(log_dir):
        return JSONResponse({
            'success': True,
            'log_files': [],
            'total': 0
        })
    
    # Get all log files
    log_files = []
    for log_file in sorted(glob.glob(os.path.join(log_dir, "*.log")), reverse=True):
        file_stats = os.stat(log_file)
        file_size_mb = file_stats.st_size / (1024 * 1024)
        modified_time = datetime.fromtimestamp(file_stats.st_mtime)
        
        log_files.append({
            'filename': os.path.basename(log_file),
            'path': log_file,
            'size_mb': round(file_size_mb, 2),
            'modified': modified_time.isoformat(),
            'modified_readable': modified_time.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return JSONResponse({
        'success': True,
        'log_files': log_files,
        'total': len(log_files),
        'log_dir': log_dir
    })


@router.get("/monitoring/logs/download/{filename}")
def download_log_file(filename: str):
    """
    Download a specific log file.
    """
    import os
    from fastapi.responses import FileResponse
    
    log_dir = "logs/ffmpeg"
    log_path = os.path.join(log_dir, filename)
    
    # Security: Prevent directory traversal
    if not os.path.abspath(log_path).startswith(os.path.abspath(log_dir)):
        return JSONResponse({
            'success': False,
            'message': 'Invalid file path'
        }, status_code=400)
    
    if not os.path.exists(log_path):
        return JSONResponse({
            'success': False,
            'message': 'Log file not found'
        }, status_code=404)
    
    return FileResponse(
        path=log_path,
        filename=filename,
        media_type='text/plain'
    )
