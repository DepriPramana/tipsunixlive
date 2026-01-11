from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.media_service import media_service
from app.services.video_service import VideoService
from pydantic import BaseModel
import logging

router = APIRouter(
    prefix="/media",
    tags=["media"]
)

logger = logging.getLogger(__name__)

class GDriveDownloadRequest(BaseModel):
    url: str

@router.post("/gdrive/download")
async def download_from_gdrive(
    request: GDriveDownloadRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start background download from Google Drive"""
    
    def _download_task(url: str):
        # Download
        video_path = media_service.download_from_gdrive(url)
        if not video_path:
            logger.error(f"Failed to download from GDrive: {url}")
            return
            
        # Register to DB (including metadata & thumbnail generation)
        # Note: We need a new session here because the original one might be closed
        # But for simplicity in this synchronous wrapper, we'll try to rely on existing service pattern
        # Ideally, we should create a new db session scope here.
        # Let's import SessionLocal to be safe.
        from app.database import SessionLocal
        db_session = SessionLocal()
        try:
            video_service = VideoService(db_session)
            video_service.save_video_with_metadata(video_path, source="gdrive")
        finally:
            db_session.close()

    background_tasks.add_task(_download_task, request.url)
    return {"status": "started", "message": "Download queued in background"}

@router.delete("/{video_id}")
def delete_video(video_id: int, db: Session = Depends(get_db)):
    """Delete video and thumbnail"""
    service = VideoService(db)
    success = service.delete_video(video_id)
    if not success:
        raise HTTPException(status_code=404, detail="Video not found or failed to delete")
    return {"status": "success", "message": "Video deleted"}

@router.post("/sync")
def sync_videos(db: Session = Depends(get_db)):
    """Trigger manual sync"""
    # This invokes the logic similar to sync_videos.py but callable via API
    # We can reuse sync_videos.py logic or just reimplement brief scan here
    # reusing the script logic is better but it's a script.
    # Let's implement a quick scan here using VideoService.
    
    import os
    video_service = VideoService(db)
    scan_dirs = ["videos/uploaded", "videos/downloaded"]
    count = 0
    
    for directory in scan_dirs:
        if not os.path.exists(directory):
            continue
            
        files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
        for filename in files:
            if filename.startswith('.'): continue
            
            file_path = os.path.join(directory, filename).replace('\\', '/')
            
            # Check exist
            from app.models.video import Video
            existing = db.query(Video).filter(Video.path == file_path).first()
            
            if not existing:
                video_service.save_video_with_metadata(file_path, source="scanned")
                count += 1
            else:
                # Check if thumbnail missing and generate if needed
                if not existing.thumbnail_path or not os.path.exists(existing.thumbnail_path):
                    thumb_path = media_service.generate_thumbnail(file_path)
                    if thumb_path:
                        existing.thumbnail_path = thumb_path
                        db.commit()
                
    return {"status": "success", "added": count}
