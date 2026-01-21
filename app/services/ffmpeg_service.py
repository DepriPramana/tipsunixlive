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
        
        # Monitor thread
        self._monitoring = False
        self._monitor_thread = None
        self._start_monitor()

    def _start_monitor(self):
        """Start monitoring thread if not running"""
        import threading
        if not self._monitoring:
            self._monitoring = True
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()
    
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
                'started_at': datetime.now(),
                'retry_count': 0,
                'max_retries': 5,
                'restart_args': {
                    'video_paths': video_paths,
                    'stream_key': stream_key,
                    'loop': loop,
                    'mode': mode
                }
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
            'uptime_seconds': (datetime.now() - process_data['started_at']).total_seconds(),
            'retry_count': process_data.get('retry_count', 0),
            'max_retries': process_data.get('max_retries', 5)
        }
    
    def get_all_active_sessions(self) -> List[int]:
        """Get list of all active session IDs"""
        return list(self.active_processes.keys())
    
    def is_process_running(self, session_id: int, pid: Optional[int] = None) -> bool:
        """
        Check if FFmpeg process is still running.
        Can check via local registry or system PID.
        """
        import psutil
        
        # 1. Check local registry first
        if session_id in self.active_processes:
            process = self.active_processes[session_id]['process']
            if process.poll() is None:
                return True
        
        # 2. Check via system PID (for multi-worker support)
        if pid:
            try:
                if psutil.pid_exists(pid):
                    # verify it's actually ffmpeg
                    p = psutil.Process(pid)
                    return 'ffmpeg' in p.name().lower()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
        return False
    
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
            
            # --- New flags to fix the warning ---
            '-map', '0:v:0',           # Map ONLY the first video stream
            '-map', '0:a:0',           # Map ONLY the first audio stream
            '-map_metadata', '-1',      # Strip all metadata/cover art
            # ------------------------------------

            # Stream Copy Mode (Near 0% CPU Usage)
            # IMPORTANT: Keyframe interval CANNOT be set here with -c:v copy!
            # YouTube requires keyframe every 2-4 seconds.
            # You MUST pre-encode your videos with: -g 60 -keyint_min 60
            '-c:v', 'copy',
            '-c:a', 'copy',
            
            # Output settings
            '-f', 'flv',
            '-flvflags', 'no_duration_filesize',
            rtmp_url
        ]
        
        return cmd
    
    def start_music_playlist_stream(
        self,
        session_id: int,
        video_background_path: str,
        music_files: List[str],
        stream_key: str,
        audio_bitrate: str = "128k"
    ) -> Optional[subprocess.Popen]:
        """
        Start FFmpeg streaming dengan music playlist + video background looping.
        
        Optimized untuk CPU usage minimal dengan menggunakan:
        - Video pre-encoded: -c:v copy (no re-encoding)
        - Audio re-encode: -c:a aac (untuk compatibility)
        - Infinite loop untuk video dan audio
        
        Args:
            session_id: LiveSession ID untuk tracking
            video_background_path: Path ke video background (sudah di-encode)
            music_files: List path file musik (MP3, AAC, dll)
            stream_key: YouTube stream key
            audio_bitrate: Audio bitrate (default: 128k)
            
        Returns:
            subprocess.Popen object atau None jika gagal
        """
        
        if not video_background_path or not os.path.exists(video_background_path):
            logger.error(f"Video background not found: {video_background_path}")
            return None
        
        if not music_files:
            logger.error("No music files provided")
            return None
        
        if not stream_key:
            logger.error("No stream key provided")
            return None
        
        # Check if session already has active process
        if session_id in self.active_processes:
            logger.warning(f"Session {session_id} already has active process")
            return None
        
        try:
            # Create concat file untuk music playlist
            music_concat_file = self._create_concat_file(music_files, session_id)
            
            # Create log file
            log_file = os.path.join(
                self.log_dir,
                f"music_session_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            )
            
            # Build optimized FFmpeg command
            cmd = self._build_music_playlist_command(
                video_background_path=video_background_path,
                music_concat_file=music_concat_file,
                stream_key=stream_key,
                audio_bitrate=audio_bitrate
            )
            
            # Log command (mask stream key)
            masked_cmd = [c if 'live2/' not in c else c.replace(stream_key, '****') for c in cmd]
            logger.info(f"Starting Music Playlist Stream for session {session_id}")
            logger.info(f"Command: {' '.join(masked_cmd)}")
            logger.info(f"Video Background: {video_background_path}")
            logger.info(f"Music Files: {len(music_files)}")
            
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
                'concat_file': music_concat_file,
                'log_file': log_file,
                'log_handle': log_handle,
                'stream_key': stream_key,
                'started_at': datetime.now(),
                'type': 'music_playlist',  # Mark as music playlist stream
                'retry_count': 0,
                'max_retries': 5,
                'restart_args': {
                    'video_background_path': video_background_path,
                    'music_files': music_files,
                    'stream_key': stream_key,
                    'audio_bitrate': audio_bitrate
                }
            }
            
            logger.info(f"[OK] Music Playlist Stream started for session {session_id}")
            logger.info(f"     PID: {process.pid}")
            logger.info(f"     Log: {log_file}")
            logger.info(f"     CPU Usage: Expected 10-20% (using -c:v copy)")
            
            return process
            
        except Exception as e:
            logger.error(f"Failed to start music playlist stream for session {session_id}: {e}")
            return None
    

    def _build_music_playlist_command(
        self,
        video_background_path: str,
        music_concat_file: str,
        stream_key: str,
        audio_bitrate: str = "128k",
        sound_effect_path: Optional[str] = None,
        sound_effect_volume: float = 0.3
    ) -> List[str]:
        """
        Build optimized FFmpeg command for music playlist with optional sound effect.
        """
        
        # RTMP URL
        rtmp_url = f"rtmp://a.rtmp.youtube.com/live2/{stream_key}"
        
        # Build optimized command
        cmd = [
            FFMPEG_PATH,
            '-nostdin',              # Disable interactive stdin
            '-loglevel', 'warning',  # Only show warnings and errors
            '-fflags', '+genpts+igndts', # Force generation of PTS
            
            # Input 0: Video Background (looping)
            '-thread_queue_size', '512',
            '-stream_loop', '-1',
            '-re',
            '-i', video_background_path,
            
            # Input 1: Music Playlist (looping)
            '-thread_queue_size', '512',
            '-f', 'concat',
            '-safe', '0',
            '-stream_loop', '-1',
            '-i', music_concat_file
        ]
        
        # Input 2: Sound Effect (Optional)
        if sound_effect_path and os.path.exists(sound_effect_path):
            cmd.extend([
                '-thread_queue_size', '512',
                '-stream_loop', '-1',
                '-i', sound_effect_path
            ])
            
            # Complex filtergraph for mixing
            # [1:a]volume=1.0[music];[2:a]volume=0.3[sfx];[music][sfx]amix=inputs=2:duration=longest
            cmd.extend([
                '-filter_complex',
                f'[1:a]volume=1.0[music];[2:a]volume={sound_effect_volume}[sfx];[music][sfx]amix=inputs=2:duration=longest[outa]',
                '-map', '0:v:0',         # Video from background
                '-map', '[outa]'         # Mixed audio
            ])
        else:
            # Simple mapping if no sound effect
            cmd.extend([
                '-map', '0:v:0',         # Video from background
                '-map', '1:a:0'          # Audio from playlist
            ])

        # Common output settings
        cmd.extend([
            # Video: Copy (no re-encoding)
            '-c:v', 'copy',
            
            # Audio: Re-encode to AAC
            '-c:a', 'aac',
            '-b:a', audio_bitrate,
            '-ar', '44100',
            '-ac', '2',
            
            # Output format
            '-f', 'flv',
            '-flvflags', 'no_duration_filesize',
            rtmp_url
        ])
        
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


# ... (Previous code) 

    def _monitor_loop(self):
        """Loop tracking process health and auto-restarting"""
        import time
        logger.info("Starting FFmpeg monitor loop")
        
        while self._monitoring:
            try:
                # Copy keys to avoid modification during iteration
                active_ids = list(self.active_processes.keys())
                
                for session_id in active_ids:
                    if session_id not in self.active_processes:
                        continue
                        
                    data = self.active_processes[session_id]
                    process = data['process']
                    
                    if process.poll() is not None:
                        # Process died
                        exit_code = process.poll()
                        logger.warning(f"Session {session_id} - Process died with code {exit_code}")
                        
                        # Check retries
                        if data.get('retry_count', 0) < data.get('max_retries', 5):
                            # Attempt Restart
                            data['retry_count'] += 1
                            retry_count = data['retry_count']
                            wait_time = 5 * (2 ** (retry_count - 1))
                            
                            logger.info(f"Session {session_id} - Scheduled restart {retry_count}/{data['max_retries']} in {wait_time}s")
                            time.sleep(wait_time)
                            
                            # Check if still active (might have been stopped by user during sleep)
                            if session_id in self.active_processes:
                                self._restart_session(session_id, data)
                        else:
                            # Max retries reached
                            logger.error(f"Session {session_id} - Max retries reached. Stream failed.")
                            # Cleanup
                            self.stop_stream(session_id)
            
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
            
            time.sleep(2)

    def _restart_session(self, session_id: int, old_data: dict):
        """Restart a crashed session"""
        try:
            logger.info(f"Restarting session {session_id}...")
            
            # Cleanup old process resources
            try:
                old_data['process'].wait(timeout=1)
            except: pass
            try:
                old_data['log_handle'].close()
            except: pass
            
            # Prepare new args
            args = old_data.get('restart_args', {})
            stream_type = old_data.get('type', 'default')
            
            new_process = None
            
            if stream_type == 'music_playlist':
                new_process = self.start_music_playlist_stream(
                    session_id=session_id,
                    video_background_path=args.get('video_background_path'),
                    music_files=args.get('music_files'),
                    stream_key=args.get('stream_key'),
                    audio_bitrate=args.get('audio_bitrate', '128k')
                )
            else:
                new_process = self.start_stream(
                    session_id=session_id,
                    video_paths=args.get('video_paths'),
                    stream_key=args.get('stream_key'),
                    loop=args.get('loop', True),
                    mode=args.get('mode', 'playlist')
                )
            
            if new_process:
                # Restore retry count
                if session_id in self.active_processes:
                    self.active_processes[session_id]['retry_count'] = old_data['retry_count']
                    logger.info(f"Session {session_id} - Restart successful (New PID: {new_process.pid})")
            else:
                logger.error(f"Session {session_id} - Restart failed")
                
        except Exception as e:
            logger.error(f"Session {session_id} - Error during restart: {e}")

# Global instance
ffmpeg_service = FFmpegService()
