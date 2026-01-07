"""
FFmpeg Service untuk multiple concurrent streaming.
Mendukung dynamic stream keys dan process management.
"""
import subprocess
import tempfile
import os
import logging
from typing import List, Optional, Dict
from datetime import datetime

from app.config import FFMPEG_PATH

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FFmpegService:
    """Service untuk mengelola FFmpeg streaming processes"""
    
    def __init__(self):
        # Registry untuk tracking active processes
        # Format: {session_id: {'process': Popen, 'concat_file': path, 'log_file': path}}
        self.active_processes: Dict[int, dict] = {}
        
        # Log directory
        self.log_dir = "logs/ffmpeg"
        os.makedirs(self.log_dir, exist_ok=True)
    
    def start_stream(
        self,
        session_id: int,
        video_paths: List[str],
        stream_key: str,
        loop: bool = True,
        mode: str = 'playlist'
    ) -> Optional[subprocess.Popen]:
        """
        Start FFmpeg streaming process.
        
        Args:
            session_id: LiveSession ID untuk tracking
            video_paths: List path video untuk di-stream
            stream_key: YouTube stream key (dynamic)
            loop: Enable infinite loop (24/7)
            mode: 'single' atau 'playlist'
            
        Returns:
            subprocess.Popen object atau None jika gagal
        """
        
        if not video_paths:
            logger.error("No video paths provided")
            return None
        
        if not stream_key:
            logger.error("No stream key provided")
            return None
        
        # Check if session already has active process
        if session_id in self.active_processes:
            logger.warning(f"Session {session_id} already has active process")
            return None
        
        try:
            # Create concat file untuk FFmpeg
            concat_file = self._create_concat_file(video_paths, session_id)
            
            # Create log file
            log_file = os.path.join(
                self.log_dir,
                f"session_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            )
            
            # Build FFmpeg command
            cmd = self._build_ffmpeg_command(
                concat_file=concat_file,
                stream_key=stream_key,
                loop=loop
            )
            
            # Log command (mask stream key)
            masked_cmd = [c if 'live2/' not in c else c.replace(stream_key, '****') for c in cmd]
            logger.info(f"Starting FFmpeg for session {session_id}")
            logger.info(f"Command: {' '.join(masked_cmd)}")
            
            # Open log file
            log_handle = open(log_file, 'w')
            
            # Start FFmpeg process
            process = subprocess.Popen(
                cmd,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE
            )
            
            # Register process
            self.active_processes[session_id] = {
                'process': process,
                'concat_file': concat_file,
                'log_file': log_file,
                'log_handle': log_handle,
                'stream_key': stream_key,
                'started_at': datetime.now()
            }
            
            logger.info(f"[OK] FFmpeg started for session {session_id}")
            logger.info(f"     PID: {process.pid}")
            logger.info(f"     Log: {log_file}")
            logger.info(f"     Videos: {len(video_paths)}")
            logger.info(f"     Loop: {loop}")
            
            return process
            
        except Exception as e:
            logger.error(f"Failed to start FFmpeg for session {session_id}: {e}")
            return None
    
    def stop_stream(self, session_id: int) -> bool:
        """
        Stop FFmpeg streaming process.
        
        Args:
            session_id: LiveSession ID
            
        Returns:
            True jika berhasil, False jika gagal
        """
        
        if session_id not in self.active_processes:
            logger.error(f"Session {session_id} not found in active processes")
            return False
        
        try:
            process_data = self.active_processes[session_id]
            process = process_data['process']
            
            logger.info(f"Stopping FFmpeg for session {session_id} (PID: {process.pid})")
            
            # Send 'q' to FFmpeg for graceful shutdown
            try:
                process.stdin.write(b'q')
                process.stdin.flush()
            except:
                pass
            
            # Wait for process to terminate
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"FFmpeg didn't stop gracefully, forcing termination")
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Force killing FFmpeg process")
                    process.kill()
            
            # Close log file
            try:
                process_data['log_handle'].close()
            except:
                pass
            
            # Cleanup concat file
            try:
                if os.path.exists(process_data['concat_file']):
                    os.remove(process_data['concat_file'])
            except:
                pass
            
            # Remove from registry
            del self.active_processes[session_id]
            
            logger.info(f"[OK] FFmpeg stopped for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping FFmpeg for session {session_id}: {e}")
            return False
    
    def get_process_status(self, session_id: int) -> Optional[Dict]:
        """
        Get status of FFmpeg process.
        
        Args:
            session_id: LiveSession ID
            
        Returns:
            Dictionary dengan status info atau None
        """
        
        if session_id not in self.active_processes:
            return None
        
        process_data = self.active_processes[session_id]
        process = process_data['process']
        
        # Check if process is still running
        poll = process.poll()
        
        return {
            'session_id': session_id,
            'pid': process.pid,
            'is_running': poll is None,
            'exit_code': poll,
            'log_file': process_data['log_file'],
            'started_at': process_data['started_at'].isoformat(),
            'uptime_seconds': (datetime.now() - process_data['started_at']).total_seconds()
        }
    
    def get_all_active_sessions(self) -> List[int]:
        """Get list of all active session IDs"""
        return list(self.active_processes.keys())
    
    def is_process_running(self, session_id: int) -> bool:
        """Check if FFmpeg process is still running"""
        
        if session_id not in self.active_processes:
            return False
        
        process = self.active_processes[session_id]['process']
        return process.poll() is None
    
    def get_process_pid(self, session_id: int) -> Optional[int]:
        """Get FFmpeg process PID"""
        
        if session_id not in self.active_processes:
            return None
        
        return self.active_processes[session_id]['process'].pid
    
    def cleanup_dead_processes(self) -> int:
        """
        Cleanup processes that have terminated.
        
        Returns:
            Number of processes cleaned up
        """
        
        dead_sessions = []
        
        for session_id, process_data in self.active_processes.items():
            process = process_data['process']
            
            if process.poll() is not None:
                # Process has terminated
                dead_sessions.append(session_id)
                logger.warning(f"Found dead process for session {session_id} (exit code: {process.poll()})")
        
        # Cleanup dead processes
        for session_id in dead_sessions:
            self.stop_stream(session_id)
        
        return len(dead_sessions)
    
    def _create_concat_file(self, video_paths: List[str], session_id: int) -> str:
        """
        Create concat file untuk FFmpeg.
        
        Args:
            video_paths: List path video
            session_id: Session ID untuk naming
            
        Returns:
            Path ke concat file
        """
        
        # Create temp file
        concat_file = tempfile.NamedTemporaryFile(
            mode='w',
            delete=False,
            suffix=f'_session_{session_id}.txt',
            prefix='ffmpeg_concat_'
        )
        
        # Write video paths
        for path in video_paths:
            # Ensure path is absolute for FFmpeg
            abs_path = os.path.abspath(path)
            
            # Escape single quotes in path
            escaped_path = abs_path.replace("'", "'\\''")
            concat_file.write(f"file '{escaped_path}'\n")
        
        concat_file.close()
        
        logger.info(f"Created concat file: {concat_file.name}")
        return concat_file.name
    
    def _build_ffmpeg_command(
        self,
        concat_file: str,
        stream_key: str,
        loop: bool = True
    ) -> List[str]:
        """
        Build FFmpeg command.
        
        Args:
            concat_file: Path ke concat file
            stream_key: YouTube stream key
            loop: Enable infinite loop
            
        Returns:
            List command arguments
        """
        
        # RTMP URL
        rtmp_url = f"rtmp://a.rtmp.youtube.com/live2/{stream_key}"
        
        # Build command
        cmd = [
            FFMPEG_PATH,
            '-nostdin',              # Disable interactive stdin
            '-loglevel', 'warning',  # Only show warnings and errors
            '-re',                   # Read input at native frame rate
            '-fflags', '+genpts+igndts', # Force generation of PTS and ignore DTS for stability
            '-f', 'concat',
            '-safe', '0',
            '-stream_loop', '-1' if loop else '0',  # -1 = infinite loop
            '-i', concat_file,
            
            # Stream Copy Mode (Near 0% CPU Usage)
            '-c:v', 'copy',
            '-c:a', 'copy',
            '-b:a', '128k',          # Included as requested, though 'copy' takes priority
            '-ar', '44100',          # Included as requested, though 'copy' takes priority
            
            # Output settings
            '-f', 'flv',
            '-flvflags', 'no_duration_filesize',
            rtmp_url
        ]
        
        return cmd
    
    def get_log_content(self, session_id: int, lines: int = 50) -> Optional[str]:
        """
        Get last N lines from FFmpeg log.
        
        Args:
            session_id: LiveSession ID
            lines: Number of lines to read
            
        Returns:
            Log content atau None
        """
        
        if session_id not in self.active_processes:
            # Try to find log file in directory if session is old
            log_files = sorted([f for f in os.listdir(self.log_dir) if f.startswith(f"session_{session_id}_")])
            if not log_files:
                return None
            log_file = os.path.join(self.log_dir, log_files[-1])
        else:
            log_file = self.active_processes[session_id]['log_file']
        
        try:
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
                return ''.join(all_lines[-lines:])
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
            return None

    def get_last_error(self, session_id: int) -> Optional[str]:
        """
        Mencoba mencari pesan error terakhir di log FFmpeg.
        """
        content = self.get_log_content(session_id, lines=20)
        if not content:
            return None
        
        error_keywords = ['Error', 'failed', 'timeout', 'invalid', 'cannot', 'could not']
        lines = content.splitlines()
        
        for line in reversed(lines):
            if any(key in line.lower() for key in error_keywords):
                return line.strip()
        
        return lines[-1].strip() if lines else None


# Global instance
ffmpeg_service = FFmpegService()
