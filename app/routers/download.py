"""
Router untuk download video dari Google Drive.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import SessionLocal
from app.services.download_service import gdrive_downloader
from app.services.video_service import VideoService
from app.models.video import Video

router = APIRouter(prefix="/gdrive", tags=["Google Drive"])


# Dependency untuk database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Pydantic schemas
class GDriveDownloadRequest(BaseModel):
    """Schema untuk download video dari Google Drive"""
    gdrive_url: str
    filename: Optional[str] = None


class VideoDetailResponse(BaseModel):
    """Schema response video detail"""
    id: int
    name: str
    path: str
    source: str
    duration: str
    duration_seconds: float
    resolution: str
    width: int
    height: int
    codec: str
    fps: float
    bitrate: int
    file_size: int
    format: str
    audio_codec: str
    created_at: str
    
    class Config:
        from_attributes = True


@router.post("/download", response_model=VideoDetailResponse)
def download_from_gdrive(request: GDriveDownloadRequest, db: Session = Depends(get_db)):
    """
    Download video dari Google Drive, extract metadata, dan simpan ke database.
    
    **Proses:**
    1. Download video dari Google Drive
    2. Extract metadata menggunakan FFprobe
    3. Simpan ke database
    4. Return video detail
    
    **Request Body:**
    ```json
    {
        "gdrive_url": "https://drive.google.com/file/d/1ABC123xyz/view?usp=sharing",
        "filename": "my_video.mp4"
    }
    ```
    
    **Response:**
    ```json
    {
        "id": 5,
        "name": "my_video.mp4",
        "path": "videos/downloaded/my_video.mp4",
        "source": "gdrive",
        "duration": "03:00:00",
        "duration_seconds": 10800.0,
        "resolution": "1920x1080",
        "width": 1920,
        "height": 1080,
        "codec": "h264",
        "fps": 30.0,
        "bitrate": 2500000,
        "file_size": 52428800,
        "format": "mov,mp4,m4a,3gp,3g2,mj2",
        "audio_codec": "aac",
        "created_at": "2026-01-06T12:00:00"
    }
    ```
    """
    # Step 1: Download video
    success, metadata = gdrive_downloader.download(
        url=request.gdrive_url,
        output_filename=request.filename
    )
    
    if not success or not metadata:
        raise HTTPException(
            status_code=500,
            detail="Gagal download video dari Google Drive. Periksa URL dan pastikan file dapat diakses."
        )
    
    # Step 2 & 3: Extract metadata dan save ke database
    # (metadata sudah di-extract oleh download_service)
    video_service = VideoService(db)
    
    try:
        # Create Video object dengan metadata yang sudah ada
        video = Video(
            name=metadata['file_name'],
            path=metadata['file_path'],
            source="gdrive",
            
            # Duration
            duration=metadata['duration_formatted'],
            duration_seconds=metadata['duration'],
            
            # Video properties
            resolution=metadata.get('resolution', 'unknown'),
            width=metadata.get('width', 0),
            height=metadata.get('height', 0),
            codec=metadata.get('codec', 'unknown'),
            fps=metadata.get('fps', 0.0),
            bitrate=metadata.get('bitrate', 0),
            
            # File info
            file_size=metadata['file_size'],
            format=metadata.get('format', 'unknown'),
            
            # Audio
            audio_codec=metadata.get('audio_codec', 'unknown'),
        )
        
        db.add(video)
        db.commit()
        db.refresh(video)
        
        # Step 4: Return video detail
        return video
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Gagal save video ke database: {str(e)}"
        )


@router.get("/supported-formats")
def get_supported_formats():
    """
    Mendapatkan list format video yang didukung.
    
    **Response:**
    ```json
    {
        "formats": [".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".m4v"]
    }
    ```
    """
    from app.services.download_service import SUPPORTED_FORMATS
    return {
        "formats": SUPPORTED_FORMATS,
        "message": "Format video yang didukung untuk download"
    }

