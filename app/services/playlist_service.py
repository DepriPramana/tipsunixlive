"""
Service untuk mengelola playlist streaming video.
Mendukung mode urutan dan random dengan looping 24/7.
"""
import random
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.playlist import Playlist
from app.models.video import Video

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PlaylistService:
    """Service untuk mengelola playlist video"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_playlist(self, playlist_id: int) -> Optional[Playlist]:
        """
        Mendapatkan playlist berdasarkan ID.
        
        Args:
            playlist_id: ID playlist
            
        Returns:
            Playlist object atau None jika tidak ditemukan
        """
        return self.db.query(Playlist).filter(Playlist.id == playlist_id).first()
    
    def get_all_playlists(self, skip: int = 0, limit: int = 100) -> List[Playlist]:
        """
        Mendapatkan semua playlist.
        
        Args:
            skip: Offset untuk pagination
            limit: Limit jumlah results
            
        Returns:
            List of Playlist objects
        """
        return self.db.query(Playlist).order_by(
            Playlist.created_at.desc()
        ).offset(skip).limit(limit).all()

    
    def get_playlist_videos(self, playlist_id: int) -> List[Video]:
        """
        Mendapatkan semua video dalam playlist.
        
        Args:
            playlist_id: ID playlist
            
        Returns:
            List of Video objects
        """
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            logger.error(f"Playlist {playlist_id} tidak ditemukan")
            return []
        
        # Get videos berdasarkan video_ids
        videos = self.db.query(Video).filter(
            Video.id.in_(playlist.video_ids)
        ).all()
        
        # Sort videos sesuai urutan di playlist.video_ids
        video_dict = {video.id: video for video in videos}
        sorted_videos = [video_dict[vid] for vid in playlist.video_ids if vid in video_dict]
        
        logger.info(f"Playlist '{playlist.name}' memiliki {len(sorted_videos)} video")
        return sorted_videos
    
    def get_video_paths(self, playlist_id: int, shuffle: bool = False) -> List[str]:
        """
        Mendapatkan list path video dari playlist.
        
        Args:
            playlist_id: ID playlist
            shuffle: Jika True, acak urutan video
            
        Returns:
            List of video file paths
        """
        videos = self.get_playlist_videos(playlist_id)
        
        if not videos:
            logger.warning(f"Tidak ada video dalam playlist {playlist_id}")
            return []
        
        # Get video paths
        video_paths = [video.path for video in videos]
        
        # Shuffle jika mode random
        if shuffle:
            random.shuffle(video_paths)
            logger.info(f"Video di-shuffle untuk mode random")
        
        return video_paths
    
    def create_playlist(self, name: str, video_ids: List[int], mode: str = "sequence") -> Playlist:
        """
        Membuat playlist baru.
        
        Args:
            name: Nama playlist
            video_ids: List ID video
            mode: Mode pemutaran ('sequence' atau 'random')
            
        Returns:
            Playlist object yang baru dibuat
        """
        playlist = Playlist(
            name=name,
            mode=mode,
            video_ids=video_ids
        )
        
        self.db.add(playlist)
        self.db.commit()
        self.db.refresh(playlist)
        
        logger.info(f"Playlist '{name}' berhasil dibuat dengan {len(video_ids)} video")
        return playlist
    
    def update_playlist(self, playlist_id: int, **kwargs) -> Optional[Playlist]:
        """
        Update playlist.
        
        Args:
            playlist_id: ID playlist
            **kwargs: Field yang akan diupdate (name, mode, video_ids)
            
        Returns:
            Updated Playlist object atau None jika tidak ditemukan
        """
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            logger.error(f"Playlist {playlist_id} tidak ditemukan")
            return None
        
        for key, value in kwargs.items():
            if hasattr(playlist, key):
                setattr(playlist, key, value)
        
        self.db.commit()
        self.db.refresh(playlist)
        
        logger.info(f"Playlist {playlist_id} berhasil diupdate")
        return playlist
    
    def delete_playlist(self, playlist_id: int) -> bool:
        """
        Hapus playlist.
        
        Args:
            playlist_id: ID playlist
            
        Returns:
            True jika berhasil, False jika tidak ditemukan
        """
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            logger.error(f"Playlist {playlist_id} tidak ditemukan")
            return False
        
        self.db.delete(playlist)
        self.db.commit()
        
        logger.info(f"Playlist {playlist_id} berhasil dihapus")
        return True
    
    def add_video_to_playlist(self, playlist_id: int, video_id: int) -> bool:
        """
        Tambah video ke playlist.
        
        Args:
            playlist_id: ID playlist
            video_id: ID video yang akan ditambahkan
            
        Returns:
            True jika berhasil, False jika gagal
        """
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            logger.error(f"Playlist {playlist_id} tidak ditemukan")
            return False
        
        # Cek apakah video ada
        video = self.db.query(Video).filter(Video.id == video_id).first()
        if not video:
            logger.error(f"Video {video_id} tidak ditemukan")
            return False
        
        # Tambahkan video_id jika belum ada
        if video_id not in playlist.video_ids:
            playlist.video_ids.append(video_id)
            self.db.commit()
            logger.info(f"Video {video_id} ditambahkan ke playlist {playlist_id}")
        else:
            logger.warning(f"Video {video_id} sudah ada di playlist {playlist_id}")
        
        return True
    
    def remove_video_from_playlist(self, playlist_id: int, video_id: int) -> bool:
        """
        Hapus video dari playlist.
        
        Args:
            playlist_id: ID playlist
            video_id: ID video yang akan dihapus
            
        Returns:
            True jika berhasil, False jika gagal
        """
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            logger.error(f"Playlist {playlist_id} tidak ditemukan")
            return False
        
        if video_id in playlist.video_ids:
            playlist.video_ids.remove(video_id)
            self.db.commit()
            logger.info(f"Video {video_id} dihapus dari playlist {playlist_id}")
            return True
        else:
            logger.warning(f"Video {video_id} tidak ada di playlist {playlist_id}")
            return False
