"""
Main FastAPI application untuk YouTube Live Streaming 24/7.
"""
from fastapi import FastAPI, Depends
from app.routers import upload, live, playlist, history, web, websocket, auth
from app.routers.download import router as gdrive_router
from app.routers import dashboard, monitoring, relive  # Removed: schedule
from app.models.youtube_account import YouTubeAccount
from app.database import Base, engine
from app.services.auth_service import get_current_user_from_cookie

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="YouTube Live Streaming 24/7",
    description="API untuk mengelola live streaming YouTube dengan playlist video",
    version="1.0.0"
)

# Public routers
app.include_router(auth.router)  # Auth (Login/Logout)

# Protected routers (Redirect to /login if not authenticated)
protected_dependency = [Depends(get_current_user_from_cookie)]

app.include_router(web.router, dependencies=protected_dependency)  # Web admin dashboard
app.include_router(upload.router, dependencies=protected_dependency)
app.include_router(live.router, dependencies=protected_dependency)
app.include_router(playlist.router, dependencies=protected_dependency)
app.include_router(gdrive_router, dependencies=protected_dependency)
app.include_router(history.router, dependencies=protected_dependency)

# New routers
app.include_router(dashboard.router, dependencies=protected_dependency)  # Stream keys dashboard
app.include_router(monitoring.router, dependencies=protected_dependency)  # Live monitoring
app.include_router(relive.router, dependencies=protected_dependency)  # Re-live feature
from app.routers import youtube_accounts, users
app.include_router(youtube_accounts.router, dependencies=protected_dependency)
app.include_router(users.router, dependencies=protected_dependency)
from app.routers import settings
app.include_router(settings.router, dependencies=protected_dependency)
app.include_router(websocket.router)  # WebSocket monitoring (usually handles auth internally or via initial connection)

# Optional: YouTube API
try:
    from app.routers import youtube_api, youtube_web, media
    app.include_router(youtube_api.router, dependencies=protected_dependency)  # YouTube API endpoints
    app.include_router(youtube_web.router, dependencies=protected_dependency)  # YouTube web pages
    app.include_router(media.router, dependencies=protected_dependency)  # Media Library
except ImportError as e:
    print(f"⚠️ Failed to import YouTube modules: {e}")
    pass

# Mount static files for thumbnails
from fastapi.staticfiles import StaticFiles
import os
os.makedirs("videos", exist_ok=True)
app.mount("/videos", StaticFiles(directory="videos"), name="videos")

def cleanup_zombie_sessions():
    """Mark all 'running' sessions as 'interrupted' on startup"""
    from app.database import SessionLocal
    from app.models.live_session import LiveSession
    from datetime import datetime
    
    db = SessionLocal()
    try:
        from app.services.stream_control_service import stream_control
        
        # 1. Kill system processes that are not in DB (or if DB says they are running but they are orphans)
        print("🔍 Searching for orphaned FFmpeg processes...")
        cleanup_result = stream_control.force_cleanup_orphaned_processes(db)
        if cleanup_result['killed_count'] > 0:
            print(f"💀 Killed {cleanup_result['killed_count']} orphaned FFmpeg processes")

        # 2. Mark any remaining 'running' sessions as 'interrupted'
        zombies = db.query(LiveSession).filter(LiveSession.status == 'running').all()
        if zombies:
            print(f"🧹 Marking {len(zombies)} ghost sessions in DB as interrupted...")
            for session in zombies:
                session.status = 'interrupted'
                session.end_time = datetime.utcnow()
            db.commit()
    except Exception as e:
        print(f"❌ Error during startup cleanup: {e}")
    finally:
        db.close()

@app.on_event("startup")
async def startup_event():
    """Run tasks on startup"""
    import asyncio
    
    # Clean up old sessions first
    cleanup_zombie_sessions()
    
    try:
        from app.services.stream_control_service import health_monitor_loop
        asyncio.create_task(health_monitor_loop())
        print("🚀 Health monitor started")
    except Exception as e:
        print(f"❌ Error starting health monitor: {e}")

    except Exception as e:
        print(f"❌ Error starting health monitor: {e}")


@app.get("/")
def root():
    """Root endpoint - redirect to admin dashboard"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/admin/")


@app.get("/api")
def api_info():
    """API information"""
    return {
        "message": "YouTube Live Streaming API",
        "version": "1.0.0",
        "endpoints": {
            "admin": "/admin",
            "upload": "/upload",
            "gdrive": "/gdrive",
            "live": "/live",
            "playlists": "/playlists",
            "history": "/history",
            "docs": "/docs"
        }
    }
