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

@router.get("/", response_class=HTMLResponse)
async def list_accounts(request: Request, db: Session = Depends(get_db)):
    accounts = db.query(YouTubeAccount).all()
    return templates.TemplateResponse("youtube_accounts.html", {
        "request": request,
        "accounts": accounts
    })

@router.post("/add")
async def add_account(name: str = Form(...), db: Session = Depends(get_db)):
    # Create unique token filename
    token_filename = f"token_yt_{uuid.uuid4().hex[:8]}.pickle"
    
    # Trigger OAuth2 flow
    success = youtube_api.authenticate(token_filename=token_filename)
    
    if not success:
        raise HTTPException(400, "Failed to authenticate with YouTube")
    
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
        # Delete old token file if it's different
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
    
    return RedirectResponse(url="/dashboard/youtube-accounts", status_code=303)

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
