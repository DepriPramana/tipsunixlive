"""
Router for authentication (login/logout).
"""
from fastapi import APIRouter, Request, Depends, HTTPException, status, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import timedelta

from app.database import SessionLocal
from app.models.user import User
from app.services.auth_service import verify_password, create_access_token

router = APIRouter(tags=["Authentication"])
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render halaman login"""
    # If user is already logged in, redirect to admin
    token = request.cookies.get("access_token")
    if token:
        return RedirectResponse(url="/admin/", status_code=status.HTTP_303_SEE_OTHER)
        
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": None
    })

@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle login submission"""
    user = db.query(User).filter(User.username == username).first()
    
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Username atau password salah",
            "username": username
        })
        
    # Create access token
    access_token = create_access_token(data={"sub": user.username})
    
    # Create response and set cookie
    response = RedirectResponse(url="/admin/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=3600 * 24, # 24 hours
        samesite="lax"
    )
    return response

@router.get("/logout")
async def logout():
    """Handle logout"""
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response
