"""
Router untuk mengelola music playlist dengan video background.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from app.database import SessionLocal
from app.services.music_playlist_service import MusicPlaylistService
from app.models.music_playlist import MusicPlaylist
import os
import logging

router = APIRouter(prefix="/music-playlists", tags=["Music Playlists"])
logger = logging.getLogger(__name__)


# Dependency untuk database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Pydantic schemas
class MusicPlaylistCreate(BaseModel):
    """Schema untuk membuat music playlist"""
    name: str
    video_background_path: str
    music_files: List[str]
    mode: str = "sequence"  # 'sequence' atau 'random'


class MusicPlaylistUpdate(BaseModel):
    """Schema untuk update music playlist"""
    name: str = None
    video_background_path: str = None
    music_files: List[str] = None
    mode: str = None


class MusicPlaylistResponse(BaseModel):
    """Schema response music playlist"""
    id: int
    name: str
    video_background_path: str
    music_files: List[str]
    mode: str
    music_count: int
    created_at: str
    
    class Config:
        from_attributes = True


@router.post("/", response_model=MusicPlaylistResponse)
def create_music_playlist(playlist: MusicPlaylistCreate, db: Session = Depends(get_db)):
    """
    Membuat music playlist baru.
    
    **Request Body:**
    ```json
    {
        "name": "Lofi Hip Hop Radio",
        "video_background_path": "videos/backgrounds/lofi_background.mp4",
        "music_files": [
            "videos/music/song1.mp3",
            "videos/music/song2.mp3",
            "videos/music/song3.mp3"
        ],
        "mode": "sequence"
    }
    ```
    """
    service = MusicPlaylistService(db)
    
    # Validasi mode
    if playlist.mode not in ["sequence", "random"]:
        raise HTTPException(status_code=400, detail="Mode harus 'sequence' atau 'random'")
    
    try:
        new_playlist = service.create_music_playlist(
            name=playlist.name,
            video_background_path=playlist.video_background_path,
            music_files=playlist.music_files,
            mode=playlist.mode
        )
        return new_playlist.to_dict()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating music playlist: {e}")
        raise HTTPException(status_code=500, detail="Failed to create music playlist")


@router.get("/", response_model=List[MusicPlaylistResponse])
def get_all_music_playlists(db: Session = Depends(get_db)):
    """
    Mendapatkan semua music playlists.
    
    **Response:**
    ```json
    [
        {
            "id": 1,
            "name": "Lofi Hip Hop Radio",
            "video_background_path": "videos/backgrounds/lofi_background.mp4",
            "music_files": ["videos/music/song1.mp3", "videos/music/song2.mp3"],
            "mode": "sequence",
            "music_count": 2,
            "created_at": "2026-01-18T10:00:00"
        }
    ]
    ```
    """
    service = MusicPlaylistService(db)
    playlists = service.get_all_music_playlists()
    return [p.to_dict() for p in playlists]


@router.get("/{playlist_id}", response_model=MusicPlaylistResponse)
def get_music_playlist(playlist_id: int, db: Session = Depends(get_db)):
    """
    Mendapatkan detail music playlist berdasarkan ID.
    """
    service = MusicPlaylistService(db)
    playlist = service.get_music_playlist(playlist_id)
    
    if not playlist:
        raise HTTPException(status_code=404, detail=f"Music playlist {playlist_id} not found")
    
    return playlist.to_dict()


@router.put("/{playlist_id}", response_model=MusicPlaylistResponse)
def update_music_playlist(playlist_id: int, playlist: MusicPlaylistUpdate, db: Session = Depends(get_db)):
    """
    Update music playlist.
    
    **Request Body:**
    ```json
    {
        "name": "Updated Name",
        "mode": "random"
    }
    ```
    """
    service = MusicPlaylistService(db)
    
    # Filter out None values
    update_data = {k: v for k, v in playlist.dict().items() if v is not None}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")
    
    # Validasi mode jika ada
    if "mode" in update_data and update_data["mode"] not in ["sequence", "random"]:
        raise HTTPException(status_code=400, detail="Mode harus 'sequence' atau 'random'")
    
    updated_playlist = service.update_music_playlist(playlist_id, **update_data)
    
    if not updated_playlist:
        raise HTTPException(status_code=404, detail=f"Music playlist {playlist_id} not found")
    
    return updated_playlist.to_dict()


@router.delete("/{playlist_id}")
def delete_music_playlist(playlist_id: int, db: Session = Depends(get_db)):
    """
    Hapus music playlist.
    """
    service = MusicPlaylistService(db)
    success = service.delete_music_playlist(playlist_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Music playlist {playlist_id} not found")
    
    return {"message": f"Music playlist {playlist_id} deleted successfully"}


@router.post("/{playlist_id}/music")
def add_music_to_playlist(playlist_id: int, music_file_path: str, db: Session = Depends(get_db)):
    """
    Tambah file musik ke playlist.
    
    **Query Parameter:**
    - music_file_path: Path ke file musik
    
    **Example:**
    ```
    POST /music-playlists/1/music?music_file_path=videos/music/new_song.mp3
    ```
    """
    service = MusicPlaylistService(db)
    success = service.add_music_to_playlist(playlist_id, music_file_path)
    
    if not success:
        raise HTTPException(status_code=404, detail="Music playlist not found or file not found")
    
    return {"message": f"Music file added to playlist {playlist_id}"}


@router.delete("/{playlist_id}/music")
def remove_music_from_playlist(playlist_id: int, music_file_path: str, db: Session = Depends(get_db)):
    """
    Hapus file musik dari playlist.
    
    **Query Parameter:**
    - music_file_path: Path ke file musik
    
    **Example:**
    ```
    DELETE /music-playlists/1/music?music_file_path=videos/music/song.mp3
    ```
    """
    service = MusicPlaylistService(db)
    success = service.remove_music_from_playlist(playlist_id, music_file_path)
    
    if not success:
        raise HTTPException(status_code=404, detail="Music playlist not found or file not in playlist")
    
    return {"message": f"Music file removed from playlist {playlist_id}"}
