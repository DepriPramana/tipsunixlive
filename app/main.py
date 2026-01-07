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
from app.routers import youtube_accounts
app.include_router(youtube_accounts.router, dependencies=protected_dependency)
app.include_router(websocket.router)  # WebSocket monitoring (usually handles auth internally or via initial connection)

# Optional: YouTube API
try:
    from app.routers import youtube_api, youtube_web
    app.include_router(youtube_api.router, dependencies=protected_dependency)  # YouTube API endpoints
    app.include_router(youtube_web.router, dependencies=protected_dependency)  # YouTube web pages
except ImportError:
    pass

@app.on_event("startup")
async def startup_event():
    """Run tasks on startup"""
    import asyncio
    try:
        from app.services.stream_control_service import health_monitor_loop
        asyncio.create_task(health_monitor_loop())
        print("🚀 Health monitor started")
    except Exception as e:
        print(f"❌ Error starting health monitor: {e}")

# Optional: YouTube API (requires google-api-python-client)
try:
    from app.routers import youtube_api, youtube_web
    app.include_router(youtube_api.router)  # YouTube API endpoints
    app.include_router(youtube_web.router)  # YouTube web pages
except ImportError:
    print("⚠️  YouTube API router not loaded (google-api-python-client not installed)")
    print("   Install with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")


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
