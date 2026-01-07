"""
Utility untuk extract metadata video menggunakan FFprobe.
"""
import subprocess
import json
import logging
from typing import Dict, Optional, Tuple
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VideoMetadataExtractor:
    """Utility untuk extract metadata video menggunakan FFprobe"""
    
    def __init__(self, ffprobe_path: str = "ffprobe"):
        """
        Initialize metadata extractor.
        
        Args:
            ffprobe_path: Path ke ffprobe executable
        """
        self.ffprobe_path = ffprobe_path
    
    def extract_metadata(self, video_path: str) -> Optional[Dict]:
        """
        Extract metadata dari video file menggunakan FFprobe.
        
        Args:
            video_path: Path ke video file
            
        Returns:
            Dictionary berisi metadata atau None jika gagal
        """
        if not Path(video_path).exists():
            logger.error(f"File tidak ditemukan: {video_path}")
            return None
        
        try:
            # FFprobe command untuk get metadata
            cmd = [
                self.ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_path
            ]
            
            logger.info(f"Extracting metadata dari: {video_path}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"FFprobe error: {result.stderr}")
                return self._get_fallback_metadata(video_path)
            
            # Parse JSON output
            data = json.loads(result.stdout)
            
            # Extract metadata
            metadata = self._parse_metadata(data, video_path)
            
            logger.info(f"✅ Metadata extracted successfully")
            return metadata
            
        except subprocess.TimeoutExpired:
            logger.error("FFprobe timeout")
            return self._get_fallback_metadata(video_path)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return self._get_fallback_metadata(video_path)
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return self._get_fallback_metadata(video_path)
    
    def _parse_metadata(self, data: Dict, video_path: str) -> Dict:
        """
        Parse metadata dari FFprobe JSON output.
        
        Args:
            data: FFprobe JSON data
            video_path: Path ke video file
            
        Returns:
            Dictionary berisi metadata yang sudah di-parse
        """
        # Get format info
        format_info = data.get('format', {})
        
        # Get video stream
        video_stream = next(
            (s for s in data.get('streams', []) if s['codec_type'] == 'video'),
            None
        )
        
        # Get audio stream
        audio_stream = next(
            (s for s in data.get('streams', []) if s['codec_type'] == 'audio'),
            None
        )
        
        # Extract duration
        duration = float(format_info.get('duration', 0))
        duration_formatted = self._format_duration(duration)
        
        # Extract resolution
        width = video_stream.get('width', 0) if video_stream else 0
        height = video_stream.get('height', 0) if video_stream else 0
        resolution = f"{width}x{height}"
        
        # Extract codec
        codec = video_stream.get('codec_name', 'unknown') if video_stream else 'unknown'
        
        # Extract FPS
        fps = 0.0
        if video_stream and 'r_frame_rate' in video_stream:
            try:
                fps = eval(video_stream['r_frame_rate'])
            except:
                fps = 0.0
        
        # Extract bitrate
        bitrate = int(format_info.get('bit_rate', 0))
        
        # Extract audio info
        audio_codec = audio_stream.get('codec_name', 'unknown') if audio_stream else 'none'
        audio_bitrate = int(audio_stream.get('bit_rate', 0)) if audio_stream else 0
        
        # File info
        file_size = Path(video_path).stat().st_size
        
        metadata = {
            # Basic info
            'file_name': Path(video_path).name,
            'file_path': video_path,
            'file_size': file_size,
            'file_size_formatted': self._format_size(file_size),
            
            # Duration
            'duration': duration,
            'duration_formatted': duration_formatted,
            
            # Video info
            'resolution': resolution,
            'width': width,
            'height': height,
            'codec': codec,
            'fps': fps,
            
            # Format & bitrate
            'format': format_info.get('format_name', 'unknown'),
            'bitrate': bitrate,
            'bitrate_formatted': self._format_bitrate(bitrate),
            
            # Audio info
            'audio_codec': audio_codec,
            'audio_bitrate': audio_bitrate,
            'audio_bitrate_formatted': self._format_bitrate(audio_bitrate),
        }
        
        return metadata
    
    def _get_fallback_metadata(self, video_path: str) -> Dict:
        """
        Get basic metadata tanpa FFprobe (fallback).
        
        Args:
            video_path: Path ke video file
            
        Returns:
            Dictionary berisi basic metadata
        """
        logger.warning("Using fallback metadata (FFprobe not available)")
        
        file_path = Path(video_path)
        file_size = file_path.stat().st_size if file_path.exists() else 0
        
        return {
            'file_name': file_path.name,
            'file_path': str(video_path),
            'file_size': file_size,
            'file_size_formatted': self._format_size(file_size),
            'duration': 0,
            'duration_formatted': 'unknown',
            'resolution': 'unknown',
            'width': 0,
            'height': 0,
            'codec': 'unknown',
            'fps': 0.0,
            'format': file_path.suffix[1:] if file_path.suffix else 'unknown',
            'bitrate': 0,
            'bitrate_formatted': 'unknown',
            'audio_codec': 'unknown',
            'audio_bitrate': 0,
            'audio_bitrate_formatted': 'unknown',
        }
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration ke HH:MM:SS"""
        if seconds == 0:
            return "00:00:00"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size ke human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    def _format_bitrate(self, bitrate: int) -> str:
        """Format bitrate ke human-readable format"""
        if bitrate == 0:
            return "0 kbps"
        
        kbps = bitrate / 1000
        if kbps < 1000:
            return f"{kbps:.0f} kbps"
        else:
            mbps = kbps / 1000
            return f"{mbps:.2f} Mbps"
    
    def print_metadata(self, metadata: Dict):
        """
        Print metadata dalam format yang readable.
        
        Args:
            metadata: Dictionary metadata
        """
        print("\n" + "="*60)
        print("📹 VIDEO METADATA")
        print("="*60)
        print(f"File Name    : {metadata['file_name']}")
        print(f"File Path    : {metadata['file_path']}")
        print(f"File Size    : {metadata['file_size_formatted']}")
        print(f"Duration     : {metadata['duration_formatted']}")
        print(f"Resolution   : {metadata['resolution']}")
        print(f"Codec        : {metadata['codec']}")
        print(f"FPS          : {metadata['fps']:.2f}")
        print(f"Bitrate      : {metadata['bitrate_formatted']}")
        print(f"Format       : {metadata['format']}")
        print(f"Audio Codec  : {metadata['audio_codec']}")
        print(f"Audio Bitrate: {metadata['audio_bitrate_formatted']}")
        print("="*60 + "\n")


# Global instance
metadata_extractor = VideoMetadataExtractor()


def get_video_metadata(video_path: str) -> Optional[Dict]:
    """
    Helper function untuk extract metadata video.
    
    Args:
        video_path: Path ke video file
        
    Returns:
        Dictionary berisi metadata atau None jika gagal
    """
    return metadata_extractor.extract_metadata(video_path)
