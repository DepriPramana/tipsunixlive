"""
Service untuk download video dari Google Drive.
Support file besar dengan progress logging dan validasi format.
"""
import os
import re
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Tuple
import gdown

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Supported video formats
SUPPORTED_FORMATS = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.m4v']

# Download directory
DOWNLOAD_DIR = "videos/downloaded"


class GoogleDriveDownloader:
    """Service untuk download video dari Google Drive"""
    
    def __init__(self, download_dir: str = DOWNLOAD_DIR):
        """
        Initialize downloader.
        
        Args:
            download_dir: Directory untuk menyimpan video yang didownload
        """
        self.download_dir = download_dir
        # Create directory if not exists
        os.makedirs(self.download_dir, exist_ok=True)
        logger.info(f"Download directory: {os.path.abspath(self.download_dir)}")
    
    def extract_file_id(self, url: str) -> Optional[str]:
        """
        Extract file ID dari Google Drive URL.
        
        Supported formats:
        - https://drive.google.com/file/d/FILE_ID/view?usp=sharing
        - https://drive.google.com/open?id=FILE_ID
        - https://drive.google.com/uc?id=FILE_ID
        
        Args:
            url: Google Drive URL
            
        Returns:
            File ID atau None jika tidak valid
        """
        # Pattern 1: /file/d/FILE_ID/
        match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)
        
        # Pattern 2: ?id=FILE_ID
        match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
        if match:
            return match.group(1)
        
        # Pattern 3: Jika sudah file ID saja
        if re.match(r'^[a-zA-Z0-9_-]+$', url):
            return url
        
        logger.error(f"Tidak dapat extract file ID dari URL: {url}")
        return None
    
    def validate_video_format(self, file_path: str) -> bool:
        """
        Validasi apakah file adalah video dengan format yang didukung.
        
        Args:
            file_path: Path ke file
            
        Returns:
            True jika valid, False jika tidak
        """
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext not in SUPPORTED_FORMATS:
            logger.error(f"Format tidak didukung: {file_ext}")
            logger.info(f"Format yang didukung: {', '.join(SUPPORTED_FORMATS)}")
            return False
        
        # Check if file exists and has size > 0
        if not os.path.exists(file_path):
            logger.error(f"File tidak ditemukan: {file_path}")
            return False
        
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            logger.error(f"File kosong: {file_path}")
            return False
        
        logger.info(f"✅ Format valid: {file_ext}, Size: {self._format_size(file_size)}")
        return True
    
    def get_video_metadata(self, file_path: str) -> Dict[str, any]:
        """
        Extract metadata video menggunakan FFprobe.
        
        Args:
            file_path: Path ke video file
            
        Returns:
            Dictionary berisi metadata video
        """
        try:
            # Use ffprobe to get video metadata
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.warning("FFprobe tidak tersedia, menggunakan metadata basic")
                return self._get_basic_metadata(file_path)
            
            import json
            data = json.loads(result.stdout)
            
            # Extract video stream info
            video_stream = next((s for s in data.get('streams', []) if s['codec_type'] == 'video'), None)
            audio_stream = next((s for s in data.get('streams', []) if s['codec_type'] == 'audio'), None)
            format_info = data.get('format', {})
            
            metadata = {
                'file_name': os.path.basename(file_path),
                'file_path': file_path,
                'file_size': os.path.getsize(file_path),
                'file_size_formatted': self._format_size(os.path.getsize(file_path)),
                'duration': float(format_info.get('duration', 0)),
                'duration_formatted': self._format_duration(float(format_info.get('duration', 0))),
                'format': format_info.get('format_name', 'unknown'),
                'bitrate': int(format_info.get('bit_rate', 0)),
            }
            
            if video_stream:
                metadata.update({
                    'width': video_stream.get('width', 0),
                    'height': video_stream.get('height', 0),
                    'resolution': f"{video_stream.get('width', 0)}x{video_stream.get('height', 0)}",
                    'codec': video_stream.get('codec_name', 'unknown'),
                    'fps': eval(video_stream.get('r_frame_rate', '0/1')),
                })
            
            if audio_stream:
                metadata.update({
                    'audio_codec': audio_stream.get('codec_name', 'unknown'),
                    'audio_bitrate': int(audio_stream.get('bit_rate', 0)),
                })
            
            return metadata
            
        except Exception as e:
            logger.warning(f"Error getting metadata: {e}")
            return self._get_basic_metadata(file_path)
    
    def _get_basic_metadata(self, file_path: str) -> Dict[str, any]:
        """Get basic metadata tanpa FFprobe"""
        file_size = os.path.getsize(file_path)
        return {
            'file_name': os.path.basename(file_path),
            'file_path': file_path,
            'file_size': file_size,
            'file_size_formatted': self._format_size(file_size),
            'duration': 0,
            'duration_formatted': 'unknown',
            'format': Path(file_path).suffix[1:],
            'resolution': 'unknown',
        }
    
    def download(self, url: str, output_filename: Optional[str] = None) -> Tuple[bool, Optional[Dict]]:
        """
        Download video dari Google Drive.
        
        Args:
            url: Google Drive share URL atau file ID
            output_filename: Nama file output (optional, akan auto-detect jika None)
            
        Returns:
            Tuple (success: bool, metadata: Dict atau None)
        """
        logger.info(f"🔽 Memulai download dari Google Drive...")
        logger.info(f"URL: {url}")
        
        # Extract file ID
        file_id = self.extract_file_id(url)
        if not file_id:
            logger.error("❌ Gagal extract file ID dari URL")
            return False, None
        
        logger.info(f"File ID: {file_id}")
        
        # Prepare output path
        if output_filename:
            output_path = os.path.join(self.download_dir, output_filename)
        else:
            # gdown will auto-detect filename
            output_path = self.download_dir + "/"
        
        try:
            # Download file dengan progress
            logger.info("📥 Downloading...")
            downloaded_file = gdown.download(
                id=file_id,
                output=output_path,
                quiet=False,
                fuzzy=True  # Enable fuzzy matching untuk berbagai format URL
            )
            
            if not downloaded_file:
                logger.error("❌ Download gagal")
                return False, None
            
            logger.info(f"✅ Download selesai: {downloaded_file}")
            
            # Validate video format
            if not self.validate_video_format(downloaded_file):
                logger.error("❌ Format video tidak valid, menghapus file...")
                os.remove(downloaded_file)
                return False, None
            
            # Get metadata
            logger.info("📊 Extracting metadata...")
            metadata = self.get_video_metadata(downloaded_file)
            
            # Log metadata
            logger.info("=" * 60)
            logger.info("📹 Video Metadata:")
            logger.info(f"  File: {metadata['file_name']}")
            logger.info(f"  Size: {metadata['file_size_formatted']}")
            logger.info(f"  Duration: {metadata['duration_formatted']}")
            logger.info(f"  Resolution: {metadata.get('resolution', 'unknown')}")
            logger.info(f"  Codec: {metadata.get('codec', 'unknown')}")
            logger.info(f"  Path: {metadata['file_path']}")
            logger.info("=" * 60)
            
            return True, metadata
            
        except Exception as e:
            logger.error(f"❌ Error saat download: {e}")
            return False, None
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size ke human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration ke HH:MM:SS"""
        if seconds == 0:
            return "unknown"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"


# Global instance
gdrive_downloader = GoogleDriveDownloader()
