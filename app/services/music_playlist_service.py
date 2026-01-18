"""
Service untuk mengelola music playlist dengan video background.
"""
import os
import tempfile
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.music_playlist import MusicPlaylist

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MusicPlaylistService:
    """Service untuk mengelola music playlist"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_music_playlist(self, playlist_id: int) -> Optional[MusicPlaylist]:
        """
        Mendapatkan music playlist berdasarkan ID.
        
        Args:
            playlist_id: ID playlist
            
        Returns:
            MusicPlaylist object atau None jika tidak ditemukan
        """
        return self.db.query(MusicPlaylist).filter(MusicPlaylist.id == playlist_id).first()
    
    def get_all_music_playlists(self, skip: int = 0, limit: int = 100) -> List[MusicPlaylist]:
        """
        Mendapatkan semua music playlists.
        
        Args:
            skip: Offset untuk pagination
            limit: Limit jumlah results
            
        Returns:
            List of MusicPlaylist objects
        """
        return self.db.query(MusicPlaylist).order_by(
            MusicPlaylist.created_at.desc()
        ).offset(skip).limit(limit).all()
    
    def create_music_playlist(
        self,
        name: str,
        video_background_path: str,
        music_files: List[str],
        mode: str = "sequence",
        sound_effect_path: Optional[str] = None,
        sound_effect_volume: float = 0.3
    ) -> MusicPlaylist:
        """
        Membuat music playlist baru.
        
        Args:
            name: Nama playlist
            video_background_path: Path ke video background
            music_files: List path file musik
            mode: Mode pemutaran ('sequence' atau 'random')
            sound_effect_path: Path file sound effect (optional)
            sound_effect_volume: Volume sound effect (0.0 - 1.0)
            
        Returns:
            MusicPlaylist object yang baru dibuat
        """
        # Validate video background exists
        if not os.path.exists(video_background_path):
            raise FileNotFoundError(f"Video background not found: {video_background_path}")
        
        # Validate music files exist
        for music_file in music_files:
            if not os.path.exists(music_file):
                raise FileNotFoundError(f"Music file not found: {music_file}")
                
        # Validate sound effect if provided
        if sound_effect_path and not os.path.exists(sound_effect_path):
            raise FileNotFoundError(f"Sound effect file not found: {sound_effect_path}")
        
        playlist = MusicPlaylist(
            name=name,
            video_background_path=video_background_path,
            music_files=music_files,
            mode=mode,
            sound_effect_path=sound_effect_path,
            sound_effect_volume=sound_effect_volume
        )
        
        self.db.add(playlist)
        self.db.commit()
        self.db.refresh(playlist)
        
        logger.info(f"Music playlist '{name}' created with {len(music_files)} music files")
        return playlist
    
    def update_music_playlist(self, playlist_id: int, **kwargs) -> Optional[MusicPlaylist]:
        """
        Update music playlist.
        
        Args:
            playlist_id: ID playlist
            **kwargs: Field yang akan diupdate
            
        Returns:
            Updated MusicPlaylist object atau None jika tidak ditemukan
        """
        playlist = self.get_music_playlist(playlist_id)
        if not playlist:
            logger.error(f"Music playlist {playlist_id} not found")
            return None
        
        for key, value in kwargs.items():
            if hasattr(playlist, key):
                setattr(playlist, key, value)
        
        self.db.commit()
        self.db.refresh(playlist)
        
        logger.info(f"Music playlist {playlist_id} updated")
        return playlist
    
    def delete_music_playlist(self, playlist_id: int) -> bool:
        """
        Hapus music playlist.
        
        Args:
            playlist_id: ID playlist
            
        Returns:
            True jika berhasil, False jika tidak ditemukan
        """
        playlist = self.get_music_playlist(playlist_id)
        if not playlist:
            logger.error(f"Music playlist {playlist_id} not found")
            return False
        
        self.db.delete(playlist)
        self.db.commit()
        
        logger.info(f"Music playlist {playlist_id} deleted")
        return True
    
    def add_music_to_playlist(self, playlist_id: int, music_file_path: str) -> bool:
        """
        Tambah file musik ke playlist.
        
        Args:
            playlist_id: ID playlist
            music_file_path: Path ke file musik
            
        Returns:
            True jika berhasil, False jika gagal
        """
        playlist = self.get_music_playlist(playlist_id)
        if not playlist:
            logger.error(f"Music playlist {playlist_id} not found")
            return False
        
        # Validate file exists
        if not os.path.exists(music_file_path):
            logger.error(f"Music file not found: {music_file_path}")
            return False
        
        # Add to playlist if not already there
        if music_file_path not in playlist.music_files:
            playlist.music_files.append(music_file_path)
            self.db.commit()
            logger.info(f"Music file added to playlist {playlist_id}: {music_file_path}")
        else:
            logger.warning(f"Music file already in playlist {playlist_id}")
        
        return True
    
    def remove_music_from_playlist(self, playlist_id: int, music_file_path: str) -> bool:
        """
        Hapus file musik dari playlist.
        
        Args:
            playlist_id: ID playlist
            music_file_path: Path ke file musik
            
        Returns:
            True jika berhasil, False jika gagal
        """
        playlist = self.get_music_playlist(playlist_id)
        if not playlist:
            logger.error(f"Music playlist {playlist_id} not found")
            return False
        
        if music_file_path in playlist.music_files:
            playlist.music_files.remove(music_file_path)
            self.db.commit()
            logger.info(f"Music file removed from playlist {playlist_id}: {music_file_path}")
            return True
        else:
            logger.warning(f"Music file not in playlist {playlist_id}")
            return False
    
    def get_music_files(self, playlist_id: int, shuffle: bool = False) -> List[str]:
        """
        Mendapatkan list path file musik dari playlist.
        
        Args:
            playlist_id: ID playlist
            shuffle: Jika True, acak urutan musik
            
        Returns:
            List of music file paths
        """
        playlist = self.get_music_playlist(playlist_id)
        if not playlist:
            logger.warning(f"Music playlist {playlist_id} not found")
            return []
        
        music_files = playlist.music_files.copy()
        
        # Shuffle jika mode random
        if shuffle or playlist.mode == "random":
            import random
            random.shuffle(music_files)
            logger.info(f"Music files shuffled for random mode")
        
        return music_files
