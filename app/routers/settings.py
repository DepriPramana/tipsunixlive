import json
from fastapi import APIRouter, Depends, Request, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SystemSetting
from app.services.youtube_api_service import YouTubeAPIService, get_youtube_service
import logging

router = APIRouter(
    prefix="/admin/settings",
    tags=["Settings"]
)

templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)

CLIENT_SECRET_KEY = "google_client_secret"

@router.get("", response_class=HTMLResponse)
async def get_settings_page(request: Request, db: Session = Depends(get_db)):
    """Render the settings page."""
    # 1. Fetch Google Credentials from DB
    secret_setting = db.query(SystemSetting).filter(SystemSetting.key == CLIENT_SECRET_KEY).first()
    
    client_id = ""
    client_secret = ""
    has_secret = False

    if secret_setting and secret_setting.value:
        try:
            # DECRYPT HERE
            decrypted_value = decrypt_value(secret_setting.value)
            
            data = json.loads(decrypted_value)
            # Handle both 'installed' and 'web' formats
            config = data.get('installed') or data.get('web') or {}
            client_id = config.get('client_id', '')
            client_secret = config.get('client_secret', '')
            has_secret = True
        except json.JSONDecodeError:
            pass

    # 2. Fetch Connected Channels
    from app.models.youtube_account import YouTubeAccount
    channels = db.query(YouTubeAccount).order_by(YouTubeAccount.created_at.desc()).all()
    
    # 3. Calculate Redirect URL
    try:
        redirect_url = str(request.url_for('oauth2callback'))
    except Exception:
        # Fallback if route not found (e.g. during testing or if router not mounted yet)
        redirect_url = str(request.base_url).rstrip('/') + "/dashboard/youtube-accounts/callback"

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "has_client_secret_db": has_secret,
        "client_id": client_id,
        "client_secret": client_secret,
        "channels": channels,
        "redirect_url": redirect_url,
        "active_tab": "general"
    })

@router.post("/update-google-secret")
async def update_google_secret(
    request: Request,
    client_id: str = Form(...),
    client_secret: str = Form(...),
    db: Session = Depends(get_db)
):
    """Update Google Client Secret in Database from Form Fields."""
    try:
        if not client_id.strip() or not client_secret.strip():
             raise ValueError("Client ID and Client Secret are required.")

        # Construct standard Google JSON format
        # We use 'installed' as default for desktop/local flow which this app currently uses
        secret_json_dict = {
            "installed": {
                "client_id": client_id.strip(),
                "client_secret": client_secret.strip(),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": ["http://localhost:8080/"]
            }
        }
        
        secret_json_str = json.dumps(secret_json_dict, indent=2)
        
        # ENCRYPT HERE
        encrypted_value = encrypt_value(secret_json_str)

        # Save to DB
        setting = db.query(SystemSetting).filter(SystemSetting.key == CLIENT_SECRET_KEY).first()
        if not setting:
            setting = SystemSetting(key=CLIENT_SECRET_KEY, value=encrypted_value, description="Google OAuth2 Client Secret")
            db.add(setting)
        else:
            setting.value = encrypted_value
        
        db.commit()
        
        # Re-fetch channels for display
        from app.models.youtube_account import YouTubeAccount
        channels = db.query(YouTubeAccount).order_by(YouTubeAccount.created_at.desc()).all()
        
        # Recalculate URL for template consistency
        try:
            redirect_url = str(request.url_for('oauth2callback'))
        except:
            redirect_url = str(request.base_url).rstrip('/') + "/dashboard/youtube-accounts/callback"
        
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "has_client_secret_db": True,
            "success_message": "Google Client Secret updated successfully! (Encrypted 🔒)",
            "client_id": client_id,
            "client_secret": client_secret,
            "channels": channels,
            "redirect_url": redirect_url,
            "active_tab": "general"
        })
        
    except ValueError as e:
        from app.models.youtube_account import YouTubeAccount
        channels = db.query(YouTubeAccount).order_by(YouTubeAccount.created_at.desc()).all()
        
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "has_client_secret_db": False,
            "error_message": str(e),
            "client_id": client_id,
            "client_secret": client_secret,
            "channels": channels,
            "active_tab": "general"
        })
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        from app.models.youtube_account import YouTubeAccount
        channels = db.query(YouTubeAccount).order_by(YouTubeAccount.created_at.desc()).all()

        return templates.TemplateResponse("settings.html", {
            "request": request,
            "has_client_secret_db": False,
            "error_message": "An unexpected error occurred while saving.",
            "client_id": client_id,
            "client_secret": client_secret,
            "channels": channels,
            "active_tab": "general"
        })

@router.post("/delete-google-secret")
async def delete_google_secret(request: Request, db: Session = Depends(get_db)):
    """Delete Google Client Secret from Database."""
    try:
        db.query(SystemSetting).filter(SystemSetting.key == CLIENT_SECRET_KEY).delete()
        db.commit()
         
        return RedirectResponse(url="/admin/settings", status_code=303)
    except Exception as e:
         logger.error(f"Error deleting settings: {e}")
         return RedirectResponse(url="/admin/settings?error=failed_delete", status_code=303)
