"""
Router untuk mengelola playlist video.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from app.database import SessionLocal
from app.services.playlist_service import PlaylistService

router = APIRouter(prefix="/playlists", tags=["Playlists"])


# Dependency untuk database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Pydantic schemas
class PlaylistCreate(BaseModel):
    """Schema untuk membuat playlist"""
    name: str
    video_ids: List[int]
    mode: str = "sequence"  # 'sequence' atau 'random'


class PlaylistUpdate(BaseModel):
    """Schema untuk update playlist"""
    name: str = None
    video_ids: List[int] = None
    mode: str = None


class PlaylistResponse(BaseModel):
    """Schema response playlist"""
    id: int
    name: str
    mode: str
    video_ids: List[int]
    created_at: str
    
    class Config:
        from_attributes = True


@router.post("/", response_model=PlaylistResponse)
def create_playlist(playlist: PlaylistCreate, db: Session = Depends(get_db)):
    """
    Membuat playlist baru.
    
    **Request Body:**
    ```json
    {
        "name": "24/7 Lofi Stream",
        "video_ids": [1, 2, 3, 4],
        "mode": "sequence"
    }
    ```
    """
    service = PlaylistService(db)
    
    # Validasi mode
    if playlist.mode not in ["sequence", "random"]:
        raise HTTPException(status_code=400, detail="Mode harus 'sequence' atau 'random'")
    
    new_playlist = service.create_playlist(
        name=playlist.name,
        video_ids=playlist.video_ids,
        mode=playlist.mode
    )
    
    return new_playlist.to_dict()


@router.get("/", response_model=List[PlaylistResponse])
def get_all_playlists(db: Session = Depends(get_db)):
    """
    Mendapatkan semua playlist.
    
    **Response:**
    ```json
    [
        {
            "id": 1,
            "name": "24/7 Lofi Stream",
            "mode": "sequence",
            "video_ids": [1, 2, 3, 4],
            "created_at": "2026-01-06T12:00:00"
        }
    ]
    ```
    """
    playlists = db.query(db.query(Playlist).all())
    return [p.to_dict() for p in playlists]


@router.get("/{playlist_id}", response_model=PlaylistResponse)
def get_playlist(playlist_id: int, db: Session = Depends(get_db)):
    """
    Mendapatkan detail playlist berdasarkan ID.
    """
    service = PlaylistService(db)
    playlist = service.get_playlist(playlist_id)
    
    if not playlist:
        raise HTTPException(status_code=404, detail=f"Playlist {playlist_id} tidak ditemukan")
    
    return playlist.to_dict()


@router.put("/{playlist_id}", response_model=PlaylistResponse)
def update_playlist(playlist_id: int, playlist: PlaylistUpdate, db: Session = Depends(get_db)):
    """
    Update playlist.
    
    **Request Body:**
    ```json
    {
        "name": "Updated Name",
        "mode": "random"
    }
    ```
    """
    service = PlaylistService(db)
    
    # Filter out None values
    update_data = {k: v for k, v in playlist.dict().items() if v is not None}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="Tidak ada data untuk diupdate")
    
    # Validasi mode jika ada
    if "mode" in update_data and update_data["mode"] not in ["sequence", "random"]:
        raise HTTPException(status_code=400, detail="Mode harus 'sequence' atau 'random'")
    
    updated_playlist = service.update_playlist(playlist_id, **update_data)
    
    if not updated_playlist:
        raise HTTPException(status_code=404, detail=f"Playlist {playlist_id} tidak ditemukan")
    
    return updated_playlist.to_dict()


@router.delete("/{playlist_id}")
def delete_playlist(playlist_id: int, db: Session = Depends(get_db)):
    """
    Hapus playlist.
    """
    service = PlaylistService(db)
    success = service.delete_playlist(playlist_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Playlist {playlist_id} tidak ditemukan")
    
    return {"message": f"Playlist {playlist_id} berhasil dihapus"}


@router.post("/{playlist_id}/videos/{video_id}")
def add_video_to_playlist(playlist_id: int, video_id: int, db: Session = Depends(get_db)):
    """
    Tambah video ke playlist.
    
    **Example:**
    ```
    POST /playlists/1/videos/5
    ```
    """
    service = PlaylistService(db)
    success = service.add_video_to_playlist(playlist_id, video_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Playlist atau video tidak ditemukan")
    
    return {"message": f"Video {video_id} ditambahkan ke playlist {playlist_id}"}


@router.delete("/{playlist_id}/videos/{video_id}")
def remove_video_from_playlist(playlist_id: int, video_id: int, db: Session = Depends(get_db)):
    """
    Hapus video dari playlist.
    
    **Example:**
    ```
    DELETE /playlists/1/videos/5
    ```
    """
    service = PlaylistService(db)
    success = service.remove_video_from_playlist(playlist_id, video_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Playlist atau video tidak ditemukan")
    
    return {"message": f"Video {video_id} dihapus dari playlist {playlist_id}"}


# Import Playlist model untuk query
from app.models.playlist import Playlist
