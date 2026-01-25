
import sys
import logging
import time
from datetime import datetime, timezone as datetime_timezone
# Fix windows encoding
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from app.database import SessionLocal
from app.models.scheduled_live import ScheduledLive
from app.models.music_playlist import MusicPlaylist
from app.services.live_scheduler_service import live_scheduler

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def diagnose():
    db = SessionLocal()
    print("=== SCHEDULER DIAGNOSIS ===")
    
    # 1. Check Time
    local_time = datetime.now()
    utc_time = datetime.now(datetime_timezone.utc)
    print(f"Server Local Time: {local_time}")
    print(f"Server UTC Time:   {utc_time}")
    
    # 2. Check Pending Jobs
    print("\n[PENDING JOBS]")
    pending = db.query(ScheduledLive).filter(ScheduledLive.status == 'pending').all()
    
    if not pending:
        print("No pending jobs found.")
    
    for job in pending:
        print(f"\nJob ID: {job.id}")
        print(f"  Scheduled (UTC): {job.scheduled_time}")
        print(f"  Mode: {job.mode}")
        print(f"  Music Playlist ID: {job.music_playlist_id}")
        
        # Check if due
        if job.scheduled_time.replace(tzinfo=datetime_timezone.utc) <= utc_time:
             print("  --> STATUS: DUE FOR EXECUTION (Should run now)")
        else:
             print(f"  --> Status: Future (Wait {job.scheduled_time.replace(tzinfo=datetime_timezone.utc) - utc_time})")

        # Check Data Integrity
        if job.mode == 'music_playlist':
            if not job.music_playlist_id:
                print("  --> ERROR: music_playlist_id is NULL/None!")
            else:
                mp = db.query(MusicPlaylist).filter(MusicPlaylist.id == job.music_playlist_id).first()
                if not mp:
                    print(f"  --> ERROR: Music Playlist {job.music_playlist_id} not found in DB")
                else:
                    print(f"  --> Data OK. Playlist: {mp.name}")
                    
    # 3. Execution Simulation
    if len(sys.argv) > 1:
        job_id = int(sys.argv[1])
        print(f"\n[SIMULATING EXECUTION FOR JOB {job_id}]")
        try:
            # We are calling the internal method to see if it crashes
            # Note: This might actually start the stream if successful!
            print("Calling _execute_scheduled_live...")
            live_scheduler._execute_scheduled_live(job_id)
            print("Execution finished without exception.")
        except Exception as e:
            print(f"EXECUTION FAILED WITH EXCEPTION: {e}")
            import traceback
            traceback.print_exc()

    print("\nDiagnosis Complete.")
    db.close()

if __name__ == "__main__":
    diagnose()
