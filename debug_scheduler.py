
import sys
import logging
from app.database import SessionLocal
from app.services.live_scheduler_service import live_scheduler
from app.models.scheduled_live import ScheduledLive

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_execution(schedule_id):
    db = SessionLocal()
    try:
        # Get the scheduled live
        print(f"Checking schedule {schedule_id}...")
        sl = db.query(ScheduledLive).filter(ScheduledLive.id == schedule_id).first()
        
        if not sl:
            print("❌ Schedule not found")
            return

        print(f"Found schedule: {sl.id}")
        print(f"Mode: {sl.mode}")
        print(f"Music Playlist ID: {sl.music_playlist_id}")
        print(f"Status: {sl.status}")
        
        # Test execution logic directly
        print("\nAttempting dry-run of execution...")
        
        # We will NOT actually run it fully to avoid starting ffmpeg, 
        # but we will check the pre-requisites that _execute_scheduled_live checks.
        
        if sl.mode == 'music_playlist':
            if not sl.music_playlist_id:
                print("❌ ERROR: music_playlist_id is missing!")
            else:
                from app.models.music_playlist import MusicPlaylist
                mp = db.query(MusicPlaylist).filter(MusicPlaylist.id == sl.music_playlist_id).first()
                if not mp:
                    print(f"❌ ERROR: Music Playlist {sl.music_playlist_id} not found in DB")
                else:
                    print(f"✅ Music Playlist found: {mp.name}")
                    
        # Check if we can trigger it manually
        # live_scheduler._execute_scheduled_live(schedule_id) 
        # Uncomment above to forcefuly run it, but let's just inspect for now.
        
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_scheduler.py <schedule_id>")
    else:
        debug_execution(int(sys.argv[1]))
