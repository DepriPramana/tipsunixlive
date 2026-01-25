
import logging
from unittest.mock import MagicMock
from datetime import datetime, timedelta

# Mock objects
logger = logging.getLogger(__name__)

class MockLiveSession:
    def __init__(self, id, restart_count):
        self.id = id
        self.restart_count = restart_count
        self.status = 'running'
        self.max_duration_hours = 0
        self.start_time = datetime.utcnow() - timedelta(hours=2) # 2 hours uptime
        self.ffmpeg_pid = 1234
        self.last_error = None
        self.end_time = None

    def get_duration_seconds(self):
        return (datetime.utcnow() - self.start_time).total_seconds()

class MockFFmpegService:
    def cleanup_dead_processes(self):
        pass
        
    def is_process_running(self, session_id, pid):
        return True
        
    def get_process_status(self, session_id):
        # Return status showing 2 hours uptime
        return {'uptime_seconds': 7200}
        
    def get_last_error(self, session_id):
        return None

# Setup Mock DB
class MockDB:
    def __init__(self):
        self.session = MockLiveSession(1, 4) # Count 4, dangerously close to 5
        self.commited = False
        
    def query(self, model):
        return self
        
    def filter(self, *args, **kwargs):
        return self
        
    def all(self):
        return [self.session]
        
    def commit(self):
        self.commited = True
        print(f"DB Committed! New restart_count: {self.session.restart_count}")
        
    def close(self):
        pass

# Re-implement the key logic chunk for testing
def test_reset_logic():
    print("Testing reset logic...")
    
    db = MockDB()
    ffmpeg_service = MockFFmpegService()
    active_sessions = db.all()
    
    for session in active_sessions:
        is_running = ffmpeg_service.is_process_running(session.id, pid=session.ffmpeg_pid)
        
        if not is_running:
            print("Stream dead logic... (skipped)")
        elif is_running and session.restart_count > 0:
            try:
                status = ffmpeg_service.get_process_status(session.id)
                if status and status.get('uptime_seconds', 0) > 3600:
                    print(f"Session {session.id} is stable (>1h). Resetting restart count (was {session.restart_count}).")
                    session.restart_count = 0
                    db.commit()
            except Exception as e:
                print(f"Error: {e}")

    if db.session.restart_count == 0:
        print("✅ SUCCESS: restart_count reset to 0")
    else:
        print(f"❌ FAILED: restart_count is {db.session.restart_count}")

if __name__ == "__main__":
    test_reset_logic()
