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
from app.config import (
    YOUTUBE_STREAM_KEY, 
    FFMPEG_PATH,
    FFMPEG_PRESET,
    FFMPEG_MAXRATE,
    FFMPEG_BUFSIZE,
    FFMPEG_GOP
)

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
        
        # Retry logic state
        self.retry_count = 0
        self.max_retries = 5
        self.last_video_paths: List[str] = []
        self.last_loop_setting: bool = True

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
        session_id: Optional[int] = None,
        is_retry: bool = False
    ) -> bool:
        """
        Mulai streaming playlist ke YouTube dengan LiveHistory tracking.
        """
        if self.is_streaming and not is_retry:
            logger.warning("Stream sudah berjalan. Stop stream terlebih dahulu.")
            return False
        
        if not video_paths:
            logger.error("Tidak ada video untuk di-stream")
            return False
        
        if not YOUTUBE_STREAM_KEY:
            logger.error("YOUTUBE_STREAM_KEY tidak ditemukan di environment")
            return False
        
        try:
            # Save state for retry
            if not is_retry:
                self.retry_count = 0
            
            self.last_video_paths = video_paths
            self.last_loop_setting = loop
            self.current_playlist_id = playlist_id
            self.current_video_id = video_id
            self.current_session_id = session_id

            # Buat concat file
            self.concat_file = self.create_concat_file(video_paths)
            
            # Determine mode
            mode = 'playlist' if playlist_id else 'single'
            self.current_mode = mode
            
            # Log video yang akan di-stream
            action_msg = "Merestart stream" if is_retry else "Memulai stream"
            logger.info(f"{action_msg} (mode: {mode}, retry: {self.retry_count}/{self.max_retries})")
            
            # FFmpeg command untuk streaming
            cmd = [
                FFMPEG_PATH,
                '-re',  # Read input at native frame rate
                '-f', 'concat',  # Use concat demuxer
                '-safe', '0',  # Allow absolute paths
                '-stream_loop', '-1' if loop else '0',  # Loop infinitely atau sekali
                '-i', self.concat_file,  # Input concat file
                '-c:v', 'libx264',  # Video codec
                '-preset', FFMPEG_PRESET,  # Encoding preset
                '-maxrate', FFMPEG_MAXRATE,  # Max bitrate
                '-bufsize', FFMPEG_BUFSIZE,  # Buffer size
                '-pix_fmt', 'yuv420p',  # Pixel format
                '-g', FFMPEG_GOP,  # GOP size
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
            
            logger.info(f"✅ Stream started! PID: {self.process.pid}")
            
            # Start monitoring thread jika belum jalan
            self.should_monitor = True
            if not self.monitor_thread or not self.monitor_thread.is_alive():
                self.monitor_thread = threading.Thread(target=self._monitor_stream, daemon=True)
                self.monitor_thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error memulai stream: {e}")
            self.cleanup()
            return False
    
    def _monitor_stream(self):
        """
        Monitor FFmpeg process untuk detect crash dan auto-restart.
        """
        logger.info("🔍 Stream monitoring started")
        
        while self.should_monitor:
            if not self.process:
                time.sleep(1)
                continue

            # Check if process is still running
            poll_result = self.process.poll()
            
            if poll_result is not None:
                # Process has terminated
                logger.warning(f"⚠️  FFmpeg process terminated with code: {poll_result}")
                
                # Intentional stop?
                if not self.should_monitor:
                    logger.info("Monitoring stop requested. Exiting thread.")
                    break

                # Read stderr untuk error message
                try:
                    stderr = self.process.stderr.read() if self.process.stderr else ""
                    if stderr:
                        logger.error(f"FFmpeg logs: ...{stderr[-200:]}")
                except:
                    pass
                
                # CRASH DETECTED - ATTEMPT RESTART
                if self.retry_count < self.max_retries:
                    self.retry_count += 1
                    backoff_time = 5 * (2 ** (self.retry_count - 1)) # 5, 10, 20, 40, 80 seconds
                    
                    logger.warning(f"🔄 Attempting restart {self.retry_count}/{self.max_retries} in {backoff_time}s...")
                    time.sleep(backoff_time)
                    
                    # Restart using stored parameters
                    success = self.start_stream(
                        video_paths=self.last_video_paths,
                        playlist_id=self.current_playlist_id,
                        video_id=self.current_video_id,
                        loop=self.last_loop_setting,
                        session_id=self.current_session_id,
                        is_retry=True
                    )
                    
                    if success:
                        logger.info("✅ Auto-restart successful")
                        continue
                    else:
                        logger.error("❌ Auto-restart failed")
                else:
                    logger.error("❌ Max retries reached. Stream permanently failed.")
                
                # If we get here, restart failed or max retries reached
                self.is_streaming = False
                self.should_monitor = False
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
        if not self.is_streaming and not self.process:
            logger.warning("Tidak ada stream yang berjalan")
            return False
        
        try:
            logger.info(f"Menghentikan stream (Session ID: {self.current_session_id})...")
            
            # Stop monitoring
            self.should_monitor = False
            
            if self.process:
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
        Manual restart streaming (stop kemudian start lagi).
        """
        logger.info("Melakukan restart stream...")
        
        if self.is_streaming:
            self.stop_stream()
            time.sleep(2)  # Wait sebentar sebelum start lagi
        
        return self.start_stream(video_paths, playlist_id)


# Global instance
stream_service = StreamService()

