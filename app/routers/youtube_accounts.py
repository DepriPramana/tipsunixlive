from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
import uuid
from datetime import datetime

from app.database import SessionLocal
from app.models.youtube_account import YouTubeAccount
from app.services.youtube_api_service import youtube_api

router = APIRouter(prefix="/dashboard/youtube-accounts", tags=["YouTube Accounts"])
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def list_accounts(request: Request, db: Session = Depends(get_db)):
    accounts = db.query(YouTubeAccount).all()
    
    # Calculate callback URL for display
    # This might need adjustment if behind a proxy that strips https
    callback_url = str(request.url_for('oauth2callback'))
    
    return templates.TemplateResponse("youtube_accounts.html", {
        "request": request,
        "accounts": accounts,
        "callback_url": callback_url
    })

@router.post("/add")
async def add_account(request: Request, name: str = Form(...), db: Session = Depends(get_db)):
    # Create unique token filename
    token_filename = f"token_yt_{uuid.uuid4().hex[:8]}.pickle"
    
    # Check if client secrets exist
    if not os.path.exists('client_secrets.json') and not os.path.exists('client_secret.json'):
         raise HTTPException(400, "client_secrets.json not found. Please upload it first.")

    # Determine redirect URI
    # Ensure usage of https scheme if behind proxy, or allow http for local dev
    # Using request.url_for is safest if configured correctly
    redirect_uri = request.url_for('oauth2callback')
    
    # Make sure we don't mix http/https if behind proxy
    # In production with SSL, this should often be forced to https
    # For now we rely on request.url_for
    
    try:
        auth_url, _ = youtube_api.get_auth_url(redirect_uri=str(redirect_uri))
    except Exception as e:
        raise HTTPException(500, f"Failed to generate auth URL: {e}")
        
    response = RedirectResponse(url=auth_url, status_code=303)
    response.set_cookie(key="pending_account_name", value=name, max_age=300) # 5 mins
    response.set_cookie(key="pending_token_filename", value=token_filename, max_age=300)
    
    return response

@router.get("/callback", name="oauth2callback")
async def oauth2callback(request: Request, db: Session = Depends(get_db)):
    code = request.query_params.get("code")
    error = request.query_params.get("error")
    
    if error:
        raise HTTPException(400, f"OAuth error: {error}")
    
    if not code:
        raise HTTPException(400, "Authorization code not found")
        
    name = request.cookies.get("pending_account_name")
    token_filename = request.cookies.get("pending_token_filename")
    
    if not name or not token_filename:
        # Fallback or error?
        # If cookies are missing (e.g. cross-site issues), we might lose context
        raise HTTPException(400, "Session expired or cookies disabled. Please try again.")

    # Reconstruct flow
    redirect_uri = request.url_for('oauth2callback')
    try:
        _, flow = youtube_api.get_auth_url(redirect_uri=str(redirect_uri))
        success = youtube_api.fetch_token_from_code(flow, code, token_filename=token_filename)
    except Exception as e:
        raise HTTPException(500, f"Authentication failed: {e}")

    if not success:
        raise HTTPException(400, "Failed to exchange code for token")
    
    # Get channel info
    channel_info = youtube_api.get_channel_info()
    
    if not channel_info:
        # Cleanup token if failed to get channel info
        if os.path.exists(token_filename):
            os.remove(token_filename)
        raise HTTPException(400, "Authenticated but failed to retrieve channel info")
    
    # Check if channel already exists
    existing_account = db.query(YouTubeAccount).filter(YouTubeAccount.channel_id == channel_info['id']).first()
    
    if existing_account:
        # Update existing account
        if existing_account.token_filename != token_filename:
            if os.path.exists(existing_account.token_filename):
                try:
                    os.remove(existing_account.token_filename)
                except:
                    pass
        
        existing_account.name = name
        existing_account.channel_title = channel_info['title']
        existing_account.token_filename = token_filename
        existing_account.last_authenticated_at = datetime.utcnow()
        existing_account.is_active = True
        
        db.commit()
    else:
        # Save new account to DB
        account = YouTubeAccount(
            name=name,
            channel_id=channel_info['id'],
            channel_title=channel_info['title'],
            token_filename=token_filename
        )
        db.add(account)
        db.commit()
    
    response = RedirectResponse(url="/dashboard/youtube-accounts", status_code=303)
    response.delete_cookie("pending_account_name")
    response.delete_cookie("pending_token_filename")
    return response

@router.post("/delete/{account_id}")
async def delete_account(account_id: int, db: Session = Depends(get_db)):
    account = db.query(YouTubeAccount).filter(YouTubeAccount.id == account_id).first()
    if account:
        # Delete token file
        if os.path.exists(account.token_filename):
            try:
                os.remove(account.token_filename)
            except:
                pass
        
        db.delete(account)
        db.commit()
        
    return RedirectResponse(url="/dashboard/youtube-accounts", status_code=303)
