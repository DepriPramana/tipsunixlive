"""
Router untuk mengelola live history dan re-live feature.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.database import SessionLocal
from app.services.live_history_service import LiveHistoryService
from app.services.playlist_service import PlaylistService
from app.services.video_service import VideoService
from app.services.scheduler import schedule_live
from app.models.live_history import LiveHistory

router = APIRouter(prefix="/history", tags=["Live History"])


# Dependency untuk database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Pydantic schemas
class HistoryResponse(BaseModel):
    """Schema response untuk history"""
    id: int
    stream_key_id: Optional[int]
    stream_key_name: Optional[str]
    mode: str
    video_id: Optional[int]
    playlist_id: Optional[int]
    start_time: str
    end_time: Optional[str]
    status: str
    duration_seconds: float
    duration_formatted: str
    
    class Config:
        from_attributes = True


class ReLiveRequest(BaseModel):
    """Schema untuk re-live (schedule ulang)"""
    history_id: int
    scheduled_time: datetime
    stream_key_id: Optional[int] = None
    max_duration_hours: Optional[int] = None

class ReStreamRequest(BaseModel):
    """Schema untuk instant re-stream (berdasarkan ID dari history mana saja)"""
    history_id: int
    stream_key_id: Optional[int] = None
    max_duration_hours: Optional[int] = None


@router.get("/", response_model=List[HistoryResponse])
def get_all_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: running, success, stopped, failed"),
    db: Session = Depends(get_db)
):
    """
    Mendapatkan semua history live streaming dengan pagination dan filter.
    
    **Query Parameters:**
    - `skip`: Offset untuk pagination (default: 0)
    - `limit`: Limit jumlah results (default: 10, max: 100)
    - `status`: Filter by status (optional)
    
    **Example:**
    ```
    GET /history?skip=0&limit=10&status=success
    ```
    
    **Response:**
    ```json
    [
        {
            "id": 5,
            "mode": "playlist",
            "video_id": null,
            "playlist_id": 1,
            "start_time": "2026-01-06T12:00:00",
            "end_time": "2026-01-06T13:30:00",
            "status": "success",
            "duration_seconds": 5400.0,
            "duration_formatted": "01:30:00"
        }
    ]
    ```
    """
    service = LiveHistoryService(db)
    sessions = service.get_all_sessions(skip=skip, limit=limit, status=status)
    
    # Convert to response format
    results = []
    for session in sessions:
        results.append({
            "id": session.id,
            "stream_key_id": session.stream_key_id,
            "stream_key_name": session.stream_key_rel.name if session.stream_key_rel else None,
            "mode": session.mode,
            "video_id": session.video_id,
            "playlist_id": session.playlist_id,
            "start_time": session.start_time.isoformat() if session.start_time else None,
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "status": session.status,
            "duration_seconds": session.get_duration_seconds(),
            "duration_formatted": session.get_duration_formatted()
        })
    
    return results


    return result


@router.delete("/{history_id}")
def delete_history(history_id: int, db: Session = Depends(get_db)):
    """
    Menghapus history streaming berdasarkan ID.
    Mendukung penghapusan dari LiveHistory dan LiveSession.
    """
    service = LiveHistoryService(db)
    success = service.delete_session(history_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"History {history_id} tidak ditemukan")
    
    return {"success": True, "message": f"History {history_id} berhasil dihapus"}


@router.get("/{history_id}")
def get_history_detail(history_id: int, db: Session = Depends(get_db)):
    """
    Mendapatkan detail history berdasarkan ID dengan info video/playlist.
    """
    service = LiveHistoryService(db)
    
    # We need to handle both LiveHistory and LiveSession
    from app.models.live_history import LiveHistory
    from app.models.live_session import LiveSession
    
    session = db.query(LiveHistory).filter(LiveHistory.id == history_id).first()
    if not session:
        session = db.query(LiveSession).filter(LiveSession.id == history_id).first()
        
    if not session:
        raise HTTPException(status_code=404, detail=f"History {history_id} tidak ditemukan")
    
    # Get additional info
    result = {
        "id": session.id,
        "mode": session.mode,
        "video_id": session.video_id,
        "playlist_id": session.playlist_id,
        "stream_key_id": session.stream_key_id,
        "start_time": session.start_time.isoformat() if session.start_time else None,
        "end_time": session.end_time.isoformat() if session.end_time else None,
        "max_duration_hours": session.max_duration_hours,
        "status": session.status,
        "duration": session.get_duration_formatted(),
        "duration_seconds": session.get_duration_seconds(),
    }
    
    # Add playlist/video info
    if session.mode == 'playlist' and session.playlist_id:
        playlist_service = PlaylistService(db)
        playlist = playlist_service.get_playlist(session.playlist_id)
        if playlist:
            result["playlist_name"] = playlist.name
            result["video_count"] = len(playlist.video_ids)
    
    elif session.mode == 'single' and session.video_id:
        video_service = VideoService(db)
        video = video_service.get_video(session.video_id)
        if video:
            result["video_name"] = video.name
            result["video_duration"] = video.duration
    
    return result


@router.post("/re-live")
def schedule_re_live(request: ReLiveRequest, db: Session = Depends(get_db)):
    """
    Menjadwalkan ulang live streaming berdasarkan history.
    Mendukung single video & playlist.
    """
    # Get history
    service = LiveHistoryService(db)
    session = service.get_session(request.history_id)
    
    if not session:
        # Fallback to LiveSession if not in LiveHistory
        from app.models.live_session import LiveSession
        session = db.query(LiveSession).filter(LiveSession.id == request.history_id).first()
        
    if not session:
        raise HTTPException(status_code=404, detail=f"History {request.history_id} tidak ditemukan")
    
    # Validate scheduled time (must be in future)
    if request.scheduled_time <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="Scheduled time harus di masa depan")
    
    # Prepare response
    response = {
        "status": "scheduled",
        "history_id": session.id,
        "mode": session.mode,
        "scheduled_time": request.scheduled_time.isoformat()
    }
    
    # Schedule based on mode
    max_dur = request.max_duration_hours if request.max_duration_hours is not None else getattr(session, 'max_duration_hours', 0)
    
    if session.mode == 'playlist' and session.playlist_id:
        # Get playlist
        playlist_service = PlaylistService(db)
        playlist = playlist_service.get_playlist(session.playlist_id)
        
        if not playlist:
            raise HTTPException(status_code=404, detail=f"Playlist {session.playlist_id} tidak ditemukan")
        
        # Get video paths
        shuffle = (playlist.mode == "random")
        video_paths = playlist_service.get_video_paths(session.playlist_id, shuffle=shuffle)
        
        if not video_paths:
            raise HTTPException(status_code=400, detail="Playlist tidak memiliki video")
        
        # Schedule live
        schedule_live(
            run_time=request.scheduled_time,
            video_paths=video_paths,
            playlist_id=session.playlist_id,
            stream_key_id=request.stream_key_id or getattr(session, 'stream_key_id', None),
            max_duration_hours=max_dur
        )
        
        response["playlist_id"] = session.playlist_id
        response["playlist_name"] = playlist.name
        response["video_count"] = len(video_paths)
        response["message"] = f"Playlist '{playlist.name}' berhasil dijadwalkan untuk {request.scheduled_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    elif session.mode == 'single' and session.video_id:
        # Get video
        video_service = VideoService(db)
        video = video_service.get_video(session.video_id)
        
        if not video:
            raise HTTPException(status_code=404, detail=f"Video {session.video_id} tidak ditemukan")
        
        # Schedule live
        schedule_live(
            run_time=request.scheduled_time,
            video_paths=[video.path],
            video_id=session.video_id,
            stream_key_id=request.stream_key_id or getattr(session, 'stream_key_id', None),
            max_duration_hours=max_dur
        )
        
        response["video_id"] = session.video_id
        response["video_name"] = video.name
        response["message"] = f"Video '{video.name}' berhasil dijadwalkan untuk {request.scheduled_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    else:
        raise HTTPException(status_code=400, detail="Invalid history: no video or playlist found")
    
    return response


@router.post("/instant-re-live")
def instant_re_live(request: ReStreamRequest, db: Session = Depends(get_db)):
    """
    Memulai ulang live streaming secara instan berdasarkan history.
    Mendukung sesion dari LiveHistory (lama) maupun LiveSession (baru).
    Akan otomatis menggunakan Stream Key yang sama jika masih ada dan aktif.
    """
    from app.models.live_session import LiveSession
    from app.services.stream_control_service import StreamControlService
    from app.routers.live import ManualLiveRequest, start_manual_live
    
    # 1. Cari data original (cek kedua table)
    # Coba di LiveHistory dulu
    history_service = LiveHistoryService(db)
    original = db.query(LiveHistory).filter(LiveHistory.id == request.history_id).first()
    
    # Jika tidak ada, coba di LiveSession
    if not original:
        original = db.query(LiveSession).filter(LiveSession.id == request.history_id).first()
        
    if not original:
        raise HTTPException(status_code=404, detail=f"Data history {request.history_id} tidak ditemukan")
        
    # 2. Get Stream Key
    # Gunakan stream_key_id dari request jika ada, jika tidak gunakan dari original, jika tidak ada lagi cari default
    stream_key_id = request.stream_key_id
    
    if not stream_key_id:
        stream_key_id = getattr(original, 'stream_key_id', None)
    
    # Jika tidak ada stream_key_id (legacy), coba cari stream key default yang aktif
    from app.models.stream_key import StreamKey
    if not stream_key_id:
        active_key = db.query(StreamKey).filter(StreamKey.is_active == True).first()
        if not active_key:
            raise HTTPException(status_code=400, detail="Tidak ada Stream Key aktif untuk melakukan Re-Stream")
        stream_key_id = active_key.id
    else:
        # Pastikan key masih ada dan aktif
        key = db.query(StreamKey).filter(StreamKey.id == stream_key_id).first()
        if not key or not key.is_active:
             # Jika key yang dipilih/lama tidak ada/mati, gunakan yang default aktif saja daripada error
             active_key = db.query(StreamKey).filter(StreamKey.is_active == True).first()
             if not active_key:
                 raise HTTPException(status_code=400, detail="Stream Key yang dipilih tidak aktif dan tidak ada key cadangan")
             stream_key_id = active_key.id

    # 3. Create Manual Request
    max_dur = request.max_duration_hours if request.max_duration_hours is not None else getattr(original, 'max_duration_hours', 0)
    
    manual_request = ManualLiveRequest(
        stream_key_id=stream_key_id,
        video_id=getattr(original, 'video_id', None),
        playlist_id=getattr(original, 'playlist_id', None),
        mode=original.mode,
        loop=True,
        max_duration_hours=max_dur,
        youtube_id=getattr(original, 'youtube_id', None)
    )
    
    # 4. Trigger start_manual_live logic
    # Kita panggil fungsinya langsung agar tidak duplikasi logic validasi concurrent
    return start_manual_live(manual_request, db)


@router.get("/statistics/summary")
def get_statistics(db: Session = Depends(get_db)):
    """
    Mendapatkan statistik streaming.
    
    **Response:**
    ```json
    {
        "total_sessions": 100,
        "success_sessions": 85,
        "failed_sessions": 10,
        "active_sessions": 1,
        "success_rate": 85.0,
        "total_streaming_hours": 450.5
    }
    ```
    """
    service = LiveHistoryService(db)
    stats = service.get_statistics()
    
    # Calculate total streaming hours
    sessions = service.get_all_sessions(limit=1000)
    total_seconds = sum(s.get_duration_seconds() for s in sessions if s.status in ['success', 'stopped'])
    total_hours = total_seconds / 3600
    
    stats["total_streaming_hours"] = round(total_hours, 2)
    
    return stats


@router.get("/playlist/{playlist_id}")
def get_playlist_history(
    playlist_id: int,
    db: Session = Depends(get_db)
):
    """
    Mendapatkan history untuk playlist tertentu.
    
    **Response:**
    ```json
    [
        {
            "id": 5,
            "start_time": "2026-01-06T12:00:00",
            "end_time": "2026-01-06T13:30:00",
            "status": "success",
            "duration": "01:30:00"
        }
    ]
    ```
    """
    service = LiveHistoryService(db)
    sessions = service.get_playlist_sessions(playlist_id)
    
    results = []
    for session in sessions:
        results.append({
            "id": session.id,
            "start_time": session.start_time.isoformat() if session.start_time else None,
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "status": session.status,
            "duration": session.get_duration_formatted(),
            "error_message": session.error_message
        })
    
    return results
