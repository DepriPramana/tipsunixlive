import os
import logging
import subprocess
import shutil
from typing import Optional, Tuple
import gdown
from app.config import FFMPEG_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MediaService:
    def __init__(self):
        self.download_dir = "videos/downloaded"
        self.thumbnail_dir = "videos/thumbnails"
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(self.thumbnail_dir, exist_ok=True)
        
    def download_from_gdrive(self, url: str) -> Optional[str]:
        """
        Download video from Google Drive.
        Returns the path to the downloaded file.
        """
        try:
            # Extract file ID from URL if needed, but gdown handles URL
            logger.info(f"Starting download from GDrive: {url}")
            
            output_path = os.path.join(self.download_dir, "downloading_video")
            
            # Download using gdown
            # fuzzy=True extracts ID from URL automatically
            output = gdown.download(url, output=None, quiet=False, fuzzy=True, use_cookies=False)
            
            if not output:
                logger.error("Download failed or returned empty path")
                return None
                
            # Move to download dir if gdown saved it in current dir
            filename = os.path.basename(output)
            final_path = os.path.join(self.download_dir, filename)
            
            if os.path.abspath(output) != os.path.abspath(final_path):
                shutil.move(output, final_path)
                
            logger.info(f"Download completed: {final_path}")
            return final_path
            
        except Exception as e:
            logger.error(f"Error downloading from GDrive: {e}")
            return None

    def generate_thumbnail(self, video_path: str) -> Optional[str]:
        """
        Generate thumbnail for video using FFmpeg.
        Returns the path to the thumbnail file relative to project root.
        """
        try:
            if not os.path.exists(video_path):
                logger.error(f"Video file not found: {video_path}")
                return None
                
            filename = os.path.basename(video_path)
            thumb_filename = f"{os.path.splitext(filename)[0]}.jpg"
            thumb_path = os.path.join(self.thumbnail_dir, thumb_filename)
            
            # FFmpeg command to extract frame at 1 second
            cmd = [
                FFMPEG_PATH,
                '-y',                   # Overwrite output
                '-ss', '00:00:01',      # Seek to 1 second
                '-i', video_path,       # Input file
                '-vframes', '1',        # Extract 1 frame
                '-q:v', '2',            # High quality
                thumb_path              # Output file
            ]
            
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            if os.path.exists(thumb_path):
                logger.info(f"Thumbnail generated: {thumb_path}")
                return thumb_path
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating thumbnail: {e}")
            return None

media_service = MediaService()
