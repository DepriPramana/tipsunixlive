"""
Database Update Script.
Safely creates missing tables in an existing database without overwriting data.
Usage:
    python update_db.py
"""
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base

# Import ALL models to ensure they are registered with Base.metadata
# This is critical for create_all to work correctly.
from app.models.youtube_broadcast import YouTubeBroadcast
from app.models.music_playlist import MusicPlaylist
from app.models.category import Category
from app.models.music_file import MusicFile
from app.models.setting import SystemSetting
from app.models.user import User
from app.models.youtube_account import YouTubeAccount
from app.models.video import Video
from app.models.playlist import Playlist
from app.models.live_session import LiveSession
from app.models.live_history import LiveHistory
from app.models.scheduled_live import ScheduledLive
from app.models.stream_key import StreamKey

def update_db():
    print("🔄 Checking for missing tables...")
    
    try:
        # create_all checks for table existence and only creates missing ones.
        # It does NOT update existing tables (e.g. adding columns).
        Base.metadata.create_all(bind=engine)
        
        print("✅ Database verification complete.")
        print("   - Missing tables (if any) have been created.")
        print("   - Existing tables were left untouched.")
        
        # Verify specific critical tables
        print("\n📋 Verified Tables:")
        for table in Base.metadata.sorted_tables:
            print(f"   - {table.name}")
            
    except Exception as e:
        print(f"❌ Error during update: {str(e)}")

if __name__ == "__main__":
    update_db()
