from app.database import SessionLocal
from app.models.live_session import LiveSession
import datetime

db = SessionLocal()
try:
    print(f"{'ID':<5} {'Mode':<15} {'Status':<10} {'Start (UTC)':<20} {'End (UTC)':<20} {'Duration':<10} {'Max(h)':<5} {'Key':<10}")
    print("-" * 100)
    
    # Get last 20 sessions
    sessions = db.query(LiveSession).order_by(LiveSession.id.desc()).limit(20).all()
    
    for s in sessions:
        duration_str = "-"
        if s.start_time and s.end_time:
            dur = (s.end_time - s.start_time).total_seconds()
            hours = int(dur // 3600)
            mins = int((dur % 3600) // 60)
            secs = int(dur % 60)
            duration_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
        elif s.start_time and s.status == 'running':
            dur = (datetime.datetime.utcnow() - s.start_time).total_seconds()
            hours = int(dur // 3600)
            mins = int((dur % 3600) // 60)
            secs = int(dur % 60)
            duration_str = f"Running ({hours:02d}:{mins:02d}:{secs:02d})"
            
        print(f"{s.id:<5} {s.mode:<15} {s.status:<10} {str(s.start_time)[:19]:<20} {str(s.end_time)[:19]:<20} {duration_str:<10} {s.max_duration_hours or 'Unl':<5} {s.stream_key_id:<10}")

finally:
    db.close()
