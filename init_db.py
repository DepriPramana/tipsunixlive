"""
Initial Database Migration Script.
Creates all necessary tables for the StreamLive system.

Usage:
    python init_db.py
"""
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base
from app.models.stream_key import StreamKey
from app.models.video import Video
from app.models.playlist import Playlist
from app.models.live_session import LiveSession
from app.models.live_history import LiveHistory
from app.models.scheduled_live import ScheduledLive
from app.models.youtube_broadcast import YouTubeBroadcast
from app.models.music_playlist import MusicPlaylist
from app.models.category import Category
from app.models.music_file import MusicFile
from app.models.setting import SystemSetting
from app.models.user import User
from app.models.youtube_account import YouTubeAccount

def init_db():
    print("Initializing StreamLive Database...")
    
    # Check if database file exists (for SQLite)
    from app.config import DATABASE_URL
    if DATABASE_URL.startswith("sqlite"):
        db_path = DATABASE_URL.replace("sqlite:///./", "")
        if os.path.exists(db_path):
            print(f"Database file '{db_path}' already exists.")
            confirm = input("Overwrite existing database? (y/N): ").lower()
            if confirm != 'y':
                print("Aborted.")
                return

    print("Creating all tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Tables created successfully:")
        for table in Base.metadata.sorted_tables:
            print(f"   - {table.name}")
            
        print("\nDatabase initialization completed!")
        print("You can now run 'python seed_data.py' to add sample data.")
        
    except Exception as e:
        print(f"❌ Error during initialization: {str(e)}")

if __name__ == "__main__":
    init_db()
