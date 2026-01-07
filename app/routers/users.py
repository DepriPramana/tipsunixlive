"""
Router for user management (list, add, edit, delete).
"""
from fastapi import APIRouter, Request, Depends, HTTPException, status, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.database import SessionLocal
from app.models.user import User
from app.services.auth_service import get_password_hash, get_current_user_from_cookie

router = APIRouter(prefix="/admin/users", tags=["User Management"])
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def list_users(
    request: Request, 
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user_from_cookie)
):
    """Halaman daftar user"""
    users = db.query(User).all()
    return templates.TemplateResponse("users.html", {
        "request": request,
        "users": users,
        "current_user": current_user
    })

@router.post("/add")
async def add_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    is_admin: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user_from_cookie)
):
    """Tambah user baru"""
    # Check if username exists
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        users = db.query(User).all()
        return templates.TemplateResponse("users.html", {
            "request": request,
            "users": users,
            "error": f"Username '{username}' sudah digunakan",
            "current_user": current_user
        })
    
    new_user = User(
        username=username,
        hashed_password=get_password_hash(password),
        is_admin=is_admin
    )
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/edit/{user_id}")
async def edit_user(
    request: Request,
    user_id: int,
    username: str = Form(...),
    password: Optional[str] = Form(None),
    is_admin: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user_from_cookie)
):
    """Edit user yang ada"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    
    # Check if new username is taken
    if username != user.username:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            users = db.query(User).all()
            return templates.TemplateResponse("users.html", {
                "request": request,
                "users": users,
                "error": f"Username '{username}' sudah digunakan",
                "current_user": current_user
            })
    
    user.username = username
    user.is_admin = is_admin
    if password:
        user.hashed_password = get_password_hash(password)
    
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/delete/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user_from_cookie)
):
    """Hapus user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    
    # Prevent deleting self
    if user.username == current_user:
         # In a real app, you'd show an error message
         return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)

    db.delete(user)
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)
