"""
Service untuk streaming playlist video ke YouTube menggunakan FFmpeg.
Mendukung mode urutan/random dan loop 24/7 dengan LiveHistory tracking.
"""
import subprocess
import tempfile
import os
import logging
import time
import threading
from typing import List, Optional
from pathlib import Path
from app.config import YOUTUBE_STREAM_KEY, FFMPEG_PATH

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StreamService:
    """Service untuk mengelola streaming video ke YouTube dengan history tracking"""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.concat_file: Optional[str] = None
        self.is_streaming = False
        self.current_playlist_id: Optional[int] = None
        self.current_video_id: Optional[int] = None
        self.current_mode: Optional[str] = None
        self.current_session_id: Optional[int] = None
        self.monitor_thread: Optional[threading.Thread] = None
        self.should_monitor = False
    
    def create_concat_file(self, video_paths: List[str]) -> str:
        """
        Membuat file concat untuk FFmpeg demuxer.
        
        Args:
            video_paths: List path video
            
        Returns:
            Path ke file concat yang dibuat
        """
        # Create temporary file untuk concat list
        fd, concat_file = tempfile.mkstemp(suffix='.txt', prefix='playlist_', text=True)
        
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                for video_path in video_paths:
                    # Convert to absolute path
                    abs_path = os.path.abspath(video_path)
                    # Escape special characters untuk FFmpeg
                    escaped_path = abs_path.replace('\\', '/').replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")
            
            logger.info(f"Concat file dibuat: {concat_file} dengan {len(video_paths)} video")
            return concat_file
        except Exception as e:
            logger.error(f"Error membuat concat file: {e}")
            os.close(fd)
            raise
    
    def start_stream(
        self,
        video_paths: List[str],
        playlist_id: Optional[int] = None,
        video_id: Optional[int] = None,
        loop: bool = True,
        session_id: Optional[int] = None
    ) -> bool:
        """
        Mulai streaming playlist ke YouTube dengan LiveHistory tracking.
        
        Args:
            video_paths: List path video untuk di-stream
            playlist_id: ID playlist yang sedang di-stream
            video_id: ID video (untuk single mode)
            loop: Jika True, loop playlist tanpa henti
            session_id: ID LiveHistory session untuk tracking
            
        Returns:
            True jika berhasil start, False jika gagal
        """
        if self.is_streaming:
            logger.warning("Stream sudah berjalan. Stop stream terlebih dahulu.")
            return False
        
        if not video_paths:
            logger.error("Tidak ada video untuk di-stream")
            return False
        
        if not YOUTUBE_STREAM_KEY:
            logger.error("YOUTUBE_STREAM_KEY tidak ditemukan di environment")
            return False
        
        try:
            # Buat concat file
            self.concat_file = self.create_concat_file(video_paths)
            
            # Determine mode
            mode = 'playlist' if playlist_id else 'single'
            
            # Log video yang akan di-stream
            logger.info(f"Memulai stream (mode: {mode})")
            if playlist_id:
                logger.info(f"Playlist ID: {playlist_id}")
            if video_id:
                logger.info(f"Video ID: {video_id}")
            
            for idx, path in enumerate(video_paths, 1):
                logger.info(f"  {idx}. {Path(path).name}")
            
            # FFmpeg command untuk streaming
            cmd = [
                FFMPEG_PATH,
                '-re',  # Read input at native frame rate
                '-f', 'concat',  # Use concat demuxer
                '-safe', '0',  # Allow absolute paths
                '-stream_loop', '-1' if loop else '0',  # Loop infinitely atau sekali
                '-i', self.concat_file,  # Input concat file
                '-c:v', 'libx264',  # Video codec
                '-preset', 'veryfast',  # Encoding preset
                '-maxrate', '3000k',  # Max bitrate
                '-bufsize', '6000k',  # Buffer size
                '-pix_fmt', 'yuv420p',  # Pixel format
                '-g', '50',  # GOP size
                '-c:a', 'aac',  # Audio codec
                '-b:a', '128k',  # Audio bitrate
                '-ar', '44100',  # Audio sample rate
                '-f', 'flv',  # Output format
                f'rtmp://a.rtmp.youtube.com/live2/{YOUTUBE_STREAM_KEY}'
            ]
            
            # Start FFmpeg process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Set state
            self.is_streaming = True
            self.current_playlist_id = playlist_id
            self.current_video_id = video_id
            self.current_mode = mode
            self.current_session_id = session_id
            
            logger.info(f"✅ Stream dimulai! PID: {self.process.pid}")
            logger.info(f"Mode: {'Loop 24/7' if loop else 'Play once'}")
            logger.info(f"Session ID: {session_id}")
            
            # Start monitoring thread untuk detect crash
            self.should_monitor = True
            self.monitor_thread = threading.Thread(target=self._monitor_stream, daemon=True)
            self.monitor_thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error memulai stream: {e}")
            self.cleanup()
            return False
    
    def _monitor_stream(self):
        """
        Monitor FFmpeg process untuk detect crash.
        Runs in background thread.
        """
        logger.info("🔍 Stream monitoring started")
        
        while self.should_monitor and self.process:
            # Check if process is still running
            poll_result = self.process.poll()
            
            if poll_result is not None:
                # Process has terminated
                logger.warning(f"⚠️  FFmpeg process terminated with code: {poll_result}")
                
                # Read stderr untuk error message
                try:
                    stderr = self.process.stderr.read() if self.process.stderr else ""
                    if stderr:
                        logger.error(f"FFmpeg error: {stderr[:500]}")  # Log first 500 chars
                except:
                    pass
                
                # Mark as crashed
                self.is_streaming = False
                self.should_monitor = False
                
                logger.error("❌ Stream crashed! Process terminated unexpectedly.")
                break
            
            # Sleep before next check
            time.sleep(5)
        
        logger.info("🔍 Stream monitoring stopped")
    
    def stop_stream(self) -> bool:
        """
        Stop streaming yang sedang berjalan.
        
        Returns:
            True jika berhasil stop, False jika tidak ada stream
        """
        if not self.is_streaming or not self.process:
            logger.warning("Tidak ada stream yang berjalan")
            return False
        
        try:
            logger.info(f"Menghentikan stream (Session ID: {self.current_session_id})...")
            
            # Stop monitoring
            self.should_monitor = False
            
            # Terminate process
            self.process.terminate()
            
            # Wait for process to finish (max 5 seconds)
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Process tidak terminate, melakukan kill...")
                self.process.kill()
                self.process.wait()
            
            logger.info("✅ Stream berhasil dihentikan")
            
            self.cleanup()
            return True
            
        except Exception as e:
            logger.error(f"❌ Error menghentikan stream: {e}")
            return False
    
    def cleanup(self):
        """Cleanup resources"""
        self.is_streaming = False
        self.should_monitor = False
        
        # Save session info before cleanup
        session_id = self.current_session_id
        
        self.current_playlist_id = None
        self.current_video_id = None
        self.current_mode = None
        self.current_session_id = None
        self.process = None
        
        # Hapus concat file jika ada
        if self.concat_file and os.path.exists(self.concat_file):
            try:
                os.remove(self.concat_file)
                logger.info(f"Concat file dihapus: {self.concat_file}")
            except Exception as e:
                logger.warning(f"Gagal menghapus concat file: {e}")
            self.concat_file = None
        
        return session_id
    
    def get_status(self) -> dict:
        """
        Mendapatkan status streaming.
        
        Returns:
            Dictionary berisi status streaming
        """
        is_process_running = False
        if self.process:
            is_process_running = self.process.poll() is None
        
        status = {
            "is_streaming": self.is_streaming,
            "playlist_id": self.current_playlist_id,
            "video_id": self.current_video_id,
            "mode": self.current_mode,
            "session_id": self.current_session_id,
            "process_id": self.process.pid if self.process else None,
            "process_running": is_process_running
        }
        
        return status
    
    def restart_stream(self, video_paths: List[str], playlist_id: int) -> bool:
        """
        Restart streaming (stop kemudian start lagi).
        
        Args:
            video_paths: List path video
            playlist_id: ID playlist
            
        Returns:
            True jika berhasil restart
        """
        logger.info("Melakukan restart stream...")
        
        if self.is_streaming:
            self.stop_stream()
            time.sleep(2)  # Wait sebentar sebelum start lagi
        
        return self.start_stream(video_paths, playlist_id)


# Global instance
stream_service = StreamService()

