from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import shutil
import os
from app.database import SessionLocal
from app.services.video_service import VideoService

router = APIRouter(tags=["Video Upload"])
UPLOAD_DIR = "videos/uploaded"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload video file and register it in the database.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename")
        
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    # Save file to disk
    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        
    # Register in database via VideoService
    video_service = VideoService(db)
    video = video_service.save_video_with_metadata(file_path, source="uploaded")
    
    if not video:
        # If metadata extraction or DB save fails, we still have the file but it won't show up in list
        # Ideally we'd remove the file or at least inform the user
        raise HTTPException(status_code=500, detail="Video saved but failed to register in database. Check file integrity.")
        
    return {
        "success": True,
        "message": "Video uploaded and registered successfully",
        "video_id": video.id,
        "path": video.path
    }
