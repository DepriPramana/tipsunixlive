"""
Script to sync video files on disk with the database.
Useful for identifying videos that were uploaded but not registered in the DB.
"""
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models.video import Video
from app.services.video_service import VideoService

def sync_videos():
    db = SessionLocal()
    video_service = VideoService(db)
    
    # Directories to scan
    scan_dirs = {
        "videos/uploaded": "uploaded",
        "videos/downloaded": "gdrive"
    }
    
    print("Starting video synchronization...")
    
    for directory, source in scan_dirs.items():
        if not os.path.exists(directory):
            print(f"Directory {directory} does not exist, skipping.")
            continue
            
        print(f"Scanning {directory}...")
        files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
        
        for filename in files:
            # Skip hidden files
            if filename.startswith('.'):
                continue
                
            file_path = os.path.join(directory, filename).replace('\\', '/')
            
            # Check if video already exists in DB
            existing = db.query(Video).filter(Video.path == file_path).first()
            if existing:
                continue
                
            print(f"Found orphaned video: {filename}. Registering...")
            try:
                video = video_service.save_video_with_metadata(file_path, source=source)
                if video:
                    print(f"DONE: Registered: {filename} (ID: {video.id})")
                else:
                    print(f"FAILED: Failed to extract metadata for: {filename}")
            except Exception as e:
                print(f"ERROR: Error registering {filename}: {str(e)}")
                
    db.close()
    print("Sync completed!")

if __name__ == "__main__":
    sync_videos()
