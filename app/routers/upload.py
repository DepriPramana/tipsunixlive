from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import shutil
import os
from app.database import SessionLocal
from app.services.video_service import VideoService
from app.config import VIDEO_STORAGE_PATH

from app.services.auth_service import get_current_user_from_cookie

router = APIRouter(tags=["Video Upload"])
UPLOAD_DIR = os.path.join(VIDEO_STORAGE_PATH, "uploaded")
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
    current_user: str = Depends(get_current_user_from_cookie),
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
# Music and Background Upload Directories
MUSIC_DIR = os.path.join(VIDEO_STORAGE_PATH, "music")
BACKGROUND_DIR = os.path.join(VIDEO_STORAGE_PATH, "backgrounds")
os.makedirs(MUSIC_DIR, exist_ok=True)
os.makedirs(BACKGROUND_DIR, exist_ok=True)


@router.post("/upload/music")
async def upload_music(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user_from_cookie),
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
    current_user: str = Depends(get_current_user_from_cookie),
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
async def list_background_videos(db: Session = Depends(get_db)):
    """
    List semua video background yang tersedia.
    Sekarang mengambil semua video yang terdaftar di database (uploaded, gdrive, dll)
    agar bisa digunakan sebagai background.
    """
    video_service = VideoService(db)
    videos = video_service.get_all_videos(limit=1000, source="background")
    
    files = []
    for video in videos:
        files.append({
            "filename": video.name,
            "path": video.path,
            "size": video.file_size or 0
        })
    
    return {"files": files}


# Sound Effect Upload
# Sound Effect Upload
SOUND_EFFECT_DIR = os.path.join(VIDEO_STORAGE_PATH, "sound_effects")
os.makedirs(SOUND_EFFECT_DIR, exist_ok=True)

@router.post("/upload/sound-effect")
async def upload_sound_effect(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload sound effect (ambient) file.
    Allowed formats: MP3, AAC, WAV, OGG, M4A
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
    
    file_path = os.path.join(SOUND_EFFECT_DIR, file.filename)
    
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
        "message": "Sound effect uploaded successfully",
        "filename": file.filename,
        "path": file_path,
        "size": os.path.getsize(file_path)
    }

@router.get("/sound-effects/list")
async def list_sound_effects():
    """
    List semua file sound effect yang tersedia.
    """
    if not os.path.exists(SOUND_EFFECT_DIR):
        return {"files": []}
    
    files = []
    for filename in os.listdir(SOUND_EFFECT_DIR):
        file_path = os.path.join(SOUND_EFFECT_DIR, filename)
        if os.path.isfile(file_path):
            files.append({
                "filename": filename,
                "path": file_path,
                "size": os.path.getsize(file_path)
            })
    
    return {"files": files}


@router.delete("/sound-effects/{filename}")
async def delete_sound_effect(
    filename: str,
    current_user: str = Depends(get_current_user_from_cookie)
):
    """
    Delete sound effect file.
    """
    file_path = os.path.join(SOUND_EFFECT_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        os.remove(file_path)
        return {"success": True, "message": f"Sound effect '{filename}' deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


@router.delete("/music/{filename}")
async def delete_music(
    filename: str,
    current_user: str = Depends(get_current_user_from_cookie)
):
    """
    Delete music file.
    """
    file_path = os.path.join(MUSIC_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        os.remove(file_path)
        return {"success": True, "message": f"Music file '{filename}' deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


@router.delete("/backgrounds/{filename}")
async def delete_background(
    filename: str,
    current_user: str = Depends(get_current_user_from_cookie)
):
    """
    Delete background video file.
    """
    file_path = os.path.join(BACKGROUND_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        os.remove(file_path)
        return {"success": True, "message": f"Background video '{filename}' deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")

