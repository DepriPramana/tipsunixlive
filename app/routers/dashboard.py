"""
Dashboard router untuk web UI.
"""
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.stream_key import StreamKey
from app.models.live_session import LiveSession

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
templates = Jinja2Templates(directory="templates")


def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/stream-keys", response_class=HTMLResponse)
def stream_keys_dashboard(request: Request, db: Session = Depends(get_db)):
    """
    Stream keys dashboard page.
    Shows list of stream keys with status and actions.
    """
    
    # Get all stream keys
    stream_keys = db.query(StreamKey).order_by(StreamKey.created_at.desc()).all()
    
    # Get active sessions
    active_sessions = db.query(LiveSession).filter(
        LiveSession.status == 'running'
    ).all()
    
    # Map stream key ID to active session
    active_session_map = {}
    for session in active_sessions:
        active_session_map[session.stream_key_id] = session
    
    # Prepare stream keys with status
    stream_keys_data = []
    for key in stream_keys:
        active_session = active_session_map.get(key.id)
        
        stream_keys_data.append({
            'id': key.id,
            'name': key.name,
            'stream_key': key._mask_key(),
            'is_active': key.is_active,
            'created_at': key.created_at,
            'status': 'live' if active_session else 'idle',
            'session_id': active_session.id if active_session else None,
            'ffmpeg_pid': active_session.ffmpeg_pid if active_session else None
        })
    
    return templates.TemplateResponse("stream_keys.html", {
        "request": request,
        "stream_keys": stream_keys_data,
        "total_keys": len(stream_keys),
        "active_count": len([k for k in stream_keys if k.is_active]),
        "live_count": len(active_sessions)
    })


@router.get("/stream-keys/api")
async def get_stream_keys_api(db: Session = Depends(get_db)):
    """API endpoint to get stream keys as JSON"""
    stream_keys = db.query(StreamKey).filter(StreamKey.is_active == True).all()
    return [{"id": key.id, "name": key.name} for key in stream_keys]


@router.get("/stream-keys/add", response_class=HTMLResponse)
def add_stream_key_form(request: Request):
    """Show add stream key form"""
    return templates.TemplateResponse("stream_key_form.html", {
        "request": request,
        "action": "add",
        "stream_key": None
    })


@router.post("/stream-keys/add")
def add_stream_key(
    name: str = Form(...),
    stream_key: str = Form(...),
    db: Session = Depends(get_db)
):
    """Add new stream key"""
    
    # Create new stream key
    new_key = StreamKey(
        name=name,
        stream_key=stream_key,
        is_active=True
    )
    
    db.add(new_key)
    db.commit()
    
    return RedirectResponse(url="/dashboard/stream-keys", status_code=303)


@router.get("/stream-keys/edit/{key_id}", response_class=HTMLResponse)
def edit_stream_key_form(key_id: int, request: Request, db: Session = Depends(get_db)):
    """Show edit stream key form"""
    
    stream_key = db.query(StreamKey).filter(StreamKey.id == key_id).first()
    
    if not stream_key:
        return RedirectResponse(url="/dashboard/stream-keys", status_code=303)
    
    return templates.TemplateResponse("stream_key_form.html", {
        "request": request,
        "action": "edit",
        "stream_key": stream_key
    })


@router.post("/stream-keys/edit/{key_id}")
def edit_stream_key(
    key_id: int,
    name: str = Form(...),
    stream_key: str = Form(...),
    db: Session = Depends(get_db)
):
    """Update stream key"""
    
    key = db.query(StreamKey).filter(StreamKey.id == key_id).first()
    
    if key:
        key.name = name
        key.stream_key = stream_key
        db.commit()
    
    return RedirectResponse(url="/dashboard/stream-keys", status_code=303)


@router.post("/stream-keys/toggle/{key_id}")
def toggle_stream_key(key_id: int, db: Session = Depends(get_db)):
    """Toggle stream key active status"""
    
    key = db.query(StreamKey).filter(StreamKey.id == key_id).first()
    
    if key:
        key.is_active = not key.is_active
        db.commit()
    
    return RedirectResponse(url="/dashboard/stream-keys", status_code=303)


@router.post("/stream-keys/delete/{key_id}")
def delete_stream_key(key_id: int, db: Session = Depends(get_db)):
    """Delete stream key"""
    
    key = db.query(StreamKey).filter(StreamKey.id == key_id).first()
    
    if key:
        db.delete(key)
        db.commit()
    
    return RedirectResponse(url="/dashboard/stream-keys", status_code=303)
