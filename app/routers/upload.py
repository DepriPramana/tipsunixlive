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


# Music and Background Upload Directories
MUSIC_DIR = "videos/music"
BACKGROUND_DIR = "videos/backgrounds"
os.makedirs(MUSIC_DIR, exist_ok=True)
os.makedirs(BACKGROUND_DIR, exist_ok=True)


@router.post("/upload/music")
async def upload_music(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload music file (MP3, AAC, etc.) untuk music playlist.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename")
    
    # Validate file extension
    allowed_extensions = ['.mp3', '.aac', '.m4a', '.wav', '.flac', '.ogg']
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    file_path = os.path.join(MUSIC_DIR, file.filename)
    
    # Check if file already exists
    if os.path.exists(file_path):
        raise HTTPException(
            status_code=400,
            detail=f"File '{file.filename}' already exists. Please rename or delete the existing file."
        )
    
    # Save file to disk
    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    return {
        "success": True,
        "message": "Music file uploaded successfully",
        "filename": file.filename,
        "path": file_path,
        "size": os.path.getsize(file_path)
    }


@router.post("/upload/background")
async def upload_background(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload video background untuk music playlist.
    Video harus sudah di-encode dengan codec yang sama dengan target streaming
    untuk mendapatkan CPU usage minimal (menggunakan -c:v copy).
    
    Recommended specs:
    - Resolution: 1920x1080 (1080p)
    - Codec: H.264
    - Bitrate: 3000-5000 kbps
    - Frame rate: 30fps
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename")
    
    # Validate file extension
    allowed_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.flv']
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    file_path = os.path.join(BACKGROUND_DIR, file.filename)
    
    # Check if file already exists
    if os.path.exists(file_path):
        raise HTTPException(
            status_code=400,
            detail=f"File '{file.filename}' already exists. Please rename or delete the existing file."
        )
    
    # Save file to disk
    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Optional: Register in database via VideoService for metadata
    video_service = VideoService(db)
    video = video_service.save_video_with_metadata(file_path, source="background")
    
    return {
        "success": True,
        "message": "Background video uploaded successfully",
        "filename": file.filename,
        "path": file_path,
        "size": os.path.getsize(file_path),
        "video_id": video.id if video else None
    }


@router.get("/music/list")
async def list_music_files():
    """
    List semua file musik yang tersedia.
    """
    if not os.path.exists(MUSIC_DIR):
        return {"files": []}
    
    files = []
    for filename in os.listdir(MUSIC_DIR):
        file_path = os.path.join(MUSIC_DIR, filename)
        if os.path.isfile(file_path):
            files.append({
                "filename": filename,
                "path": file_path,
                "size": os.path.getsize(file_path)
            })
    
    return {"files": files}


@router.get("/backgrounds/list")
async def list_background_videos():
    """
    List semua video background yang tersedia.
    """
    if not os.path.exists(BACKGROUND_DIR):
        return {"files": []}
    
    files = []
    for filename in os.listdir(BACKGROUND_DIR):
        file_path = os.path.join(BACKGROUND_DIR, filename)
        if os.path.isfile(file_path):
            files.append({
                "filename": filename,
                "path": file_path,
                "size": os.path.getsize(file_path)
            })
    
    return {"files": files}

