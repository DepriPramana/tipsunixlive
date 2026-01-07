"""
Router untuk YouTube API web pages.
Handles rendering Jinja2 templates untuk YouTube broadcast management.
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.youtube_account import YouTubeAccount

router = APIRouter(prefix="/admin/youtube", tags=["YouTube Web"])

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")


# Dependency untuk database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/broadcasts", response_class=HTMLResponse)
async def broadcasts_page(request: Request, db: Session = Depends(get_db)):
    """
    Halaman untuk manage YouTube broadcasts.
    
    Features:
    - List all broadcasts from YouTube
    - Filter by status
    - Delete broadcasts
    - Copy stream keys
    - View on YouTube
    """
    from app.models.stream_key import StreamKey
    
    # Get stream keys yang dibuat via YouTube API
    # (stream keys dengan nama yang mengandung broadcast info)
    youtube_stream_keys = db.query(StreamKey).filter(
        StreamKey.is_active == True
    ).order_by(StreamKey.created_at.desc()).all()
    
    # Check if YouTube API is available
    youtube_available = False
    broadcasts = []
    error_message = None
    
    # Get all YouTube accounts
    youtube_accounts = db.query(YouTubeAccount).all()
    
    # Get active account for initial load
    active_account = next((a for a in youtube_accounts if a.is_active), None)
    if not active_account and youtube_accounts:
        active_account = youtube_accounts[0]

    try:
        from app.services.youtube_api_service import youtube_api
        
        # Try to authenticate with active account if available
        if active_account:
            youtube_api.authenticate(token_filename=active_account.token_filename)
        elif not youtube_api.youtube:
            youtube_api.authenticate()
        
        if youtube_api.youtube:
            youtube_available = True
            # Get broadcasts from YouTube
            broadcasts = youtube_api.list_live_broadcasts(max_results=50)
    except ImportError:
        error_message = "YouTube API not installed. Install with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
    except FileNotFoundError as e:
        error_message = str(e)
    except Exception as e:
        error_message = f"Error connecting to YouTube API: {str(e)}"
    
    return templates.TemplateResponse("youtube_broadcasts.html", {
        "request": request,
        "broadcasts": broadcasts,
        "youtube_stream_keys": youtube_stream_keys,
        "youtube_available": youtube_available,
        "youtube_accounts": youtube_accounts,
        "active_account_id": active_account.id if active_account else None,
        "error_message": error_message
    })


@router.get("/create", response_class=HTMLResponse)
async def create_page(request: Request, db: Session = Depends(get_db)):
    """
    Halaman untuk create YouTube broadcasts.
    
    Features:
    - Create single broadcast
    - Create multiple broadcasts (batch)
    - Form validation
    - Preview before creation
    """
    # Check if YouTube API is available
    youtube_available = False
    error_message = None
    
    # Get all YouTube accounts
    youtube_accounts = db.query(YouTubeAccount).filter(YouTubeAccount.is_active == True).all()

    try:
        from app.services.youtube_api_service import youtube_api
        
        # Try to authenticate with the first active account if it exists
        if youtube_accounts:
            youtube_api.authenticate(token_filename=youtube_accounts[0].token_filename)
        elif not youtube_api.youtube:
            youtube_api.authenticate()
        
        if youtube_api.youtube:
            youtube_available = True
    except ImportError:
        error_message = "YouTube API not installed. Install with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
    except FileNotFoundError as e:
        error_message = str(e)
    except Exception as e:
        error_message = f"Error connecting to YouTube API: {str(e)}"
    
    return templates.TemplateResponse("youtube_create.html", {
        "request": request,
        "youtube_available": youtube_available,
        "youtube_accounts": youtube_accounts,
        "error_message": error_message
    })
