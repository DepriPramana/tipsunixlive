"""
Service untuk mengelola video dan metadata.
"""
import logging
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from app.models.video import Video
from app.utils.video_metadata import get_video_metadata

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VideoService:
    """Service untuk mengelola video dan metadata"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def save_video_with_metadata(
        self,
        video_path: str,
        source: str = "uploaded"
    ) -> Optional[Video]:
        """
        Extract metadata dari video dan save ke database.
        
        Args:
            video_path: Path ke video file
            source: Source video (uploaded/downloaded/gdrive)
            
        Returns:
            Video object yang sudah disave atau None jika gagal
        """
        logger.info(f"Saving video with metadata: {video_path}")
        
        # Extract metadata
        metadata = get_video_metadata(video_path)
        
        if not metadata:
            logger.error("Gagal extract metadata")
            return None
        
        try:
            # Create Video object
            video = Video(
                name=metadata['file_name'],
                path=metadata['file_path'],
                source=source,
                
                # Duration
                duration=metadata['duration_formatted'],
                duration_seconds=metadata['duration'],
                
                # Video properties
                resolution=metadata['resolution'],
                width=metadata['width'],
                height=metadata['height'],
                codec=metadata['codec'],
                fps=metadata['fps'],
                bitrate=metadata['bitrate'],
                
                # File info
                file_size=metadata['file_size'],
                format=metadata['format'],
                
                # Audio
                audio_codec=metadata['audio_codec'],
            )
            
            # Save to database
            self.db.add(video)
            self.db.commit()
            self.db.refresh(video)
            
            logger.info(f"✅ Video saved to database with ID: {video.id}")
            return video
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error saving video to database: {e}")
            return None
    
    def update_video_metadata(self, video_id: int) -> Optional[Video]:
        """
        Re-extract dan update metadata video.
        
        Args:
            video_id: ID video yang akan diupdate
            
        Returns:
            Updated Video object atau None jika gagal
        """
        video = self.db.query(Video).filter(Video.id == video_id).first()
        
        if not video:
            logger.error(f"Video {video_id} tidak ditemukan")
            return None
        
        logger.info(f"Updating metadata untuk video {video_id}")
        
        # Extract metadata
        metadata = get_video_metadata(video.path)
        
        if not metadata:
            logger.error("Gagal extract metadata")
            return None
        
        try:
            # Update fields
            video.duration = metadata['duration_formatted']
            video.duration_seconds = metadata['duration']
            video.resolution = metadata['resolution']
            video.width = metadata['width']
            video.height = metadata['height']
            video.codec = metadata['codec']
            video.fps = metadata['fps']
            video.bitrate = metadata['bitrate']
            video.file_size = metadata['file_size']
            video.format = metadata['format']
            video.audio_codec = metadata['audio_codec']
            
            self.db.commit()
            self.db.refresh(video)
            
            logger.info(f"✅ Metadata updated untuk video {video_id}")
            return video
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating metadata: {e}")
            return None
    
    def get_video(self, video_id: int) -> Optional[Video]:
        """Get video by ID"""
        return self.db.query(Video).filter(Video.id == video_id).first()
    
    def get_all_videos(self, skip: int = 0, limit: int = 100) -> List[Video]:
        """Get all videos dengan pagination"""
        return self.db.query(Video).offset(skip).limit(limit).all()
    
    def delete_video(self, video_id: int) -> bool:
        """
        Delete video dari database.
        
        Args:
            video_id: ID video yang akan dihapus
            
        Returns:
            True jika berhasil, False jika gagal
        """
        video = self.get_video(video_id)
        
        if not video:
            logger.error(f"Video {video_id} tidak ditemukan")
            return False
        
        try:
            self.db.delete(video)
            self.db.commit()
            logger.info(f"✅ Video {video_id} deleted")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting video: {e}")
            return False
