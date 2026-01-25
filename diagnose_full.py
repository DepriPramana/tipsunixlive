
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

def check_file_stats(path):
    if os.path.exists(path):
        size = os.path.getsize(path)
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        print(f"  [FILE] Found: {path}")
        print(f"  [FILE] Size: {size} bytes")
        print(f"  [FILE] Modified: {mtime}")
    else:
        print(f"  [FILE] NOT FOUND: {path}")

def diagnose():
    db = SessionLocal()
    print("=== SCHEDULER DIAGNOSIS ===")
    
    # -1. Check .env
    env_path = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_path):
        print(f"\n[ENV] Found .env at {env_path}")
        with open(env_path, 'r') as f:
            for line in f:
                if 'DATABASE_URL' in line:
                    print(f"  [ENV] {line.strip()}")
    else:
        print("\n[ENV] No .env file found in CWD")

    # 0. Check Database Path
    import os
    from app.database import engine
    print(f"Current Working Directory: {os.getcwd()}")
    print(f"Database URL: {engine.url}")
    print(f"Absolute Data DB Path (Expected): {os.path.abspath('data.db')}")
    check_file_stats(os.path.abspath('data.db'))
    
    # 1. Check Time
    local_time = datetime.now()
    utc_time = datetime.now(datetime_timezone.utc)
    print(f"Server Local Time: {local_time}")
    print(f"Server UTC Time:   {utc_time}")
    
    # 2. Check Jobs (ALL)
    print("\n[ALL JOBS QUERY]")
    all_jobs = db.query(ScheduledLive).all()
    print(f"Total jobs found in DB: {len(all_jobs)}")

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
