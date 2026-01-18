"""
API Router untuk music file management.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import os
import shutil

from app.database import SessionLocal
from app.services.music_file_service import MusicFileService


router = APIRouter(prefix="/music-files", tags=["Music Files"])

# Music directory
MUSIC_DIR = "videos/music"
os.makedirs(MUSIC_DIR, exist_ok=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class MusicFileUpdate(BaseModel):
    filename: Optional[str] = None
    category_id: Optional[int] = None
    tags: Optional[List[str]] = None


@router.get("/")
async def get_music_files(
    page: int = 1,
    limit: int = 50,
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    format: Optional[str] = None,
    sort: str = "filename",
    order: str = "asc",
    db: Session = Depends(get_db)
):
    """
    Get all music files with pagination and filters.
    
    Query Parameters:
    - page: Page number (default: 1)
    - limit: Items per page (default: 50)
    - search: Search term for filename
    - category_id: Filter by category
    - format: Filter by format
    - sort: Sort field (filename, uploaded_at, duration, file_size)
    - order: Sort order (asc, desc)
    """
    service = MusicFileService(db)
    
    music_files, total = service.get_all_music_files(
        page=page,
        limit=limit,
        search=search,
        category_id=category_id,
        format=format,
        sort=sort,
        order=order
    )
    
    return {
        "music_files": [mf.to_dict() for mf in music_files],
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit
    }


@router.get("/search")
async def search_music_files(
    q: str,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Search music files by filename or tags"""
    service = MusicFileService(db)
    music_files = service.search_music_files(q, limit)
    
    return {
        "music_files": [mf.to_dict() for mf in music_files],
        "count": len(music_files)
    }


@router.get("/formats")
async def get_formats(db: Session = Depends(get_db)):
    """Get list of unique formats"""
    service = MusicFileService(db)
    formats = service.get_formats()
    
    return {"formats": formats}


@router.get("/{music_file_id}")
async def get_music_file(music_file_id: int, db: Session = Depends(get_db)):
    """Get music file by ID"""
    service = MusicFileService(db)
    music_file = service.get_music_file(music_file_id)
    
    if not music_file:
        raise HTTPException(status_code=404, detail="Music file not found")
    
    return music_file.to_dict()


@router.post("/upload")
async def upload_music_file(
    file: UploadFile = File(...),
    category_id: Optional[int] = Form(None),
    tags: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload single music file"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename")
    
    # Validate file extension
    allowed_extensions = ['.mp3', '.aac', '.m4a', '.wav', '.flac', '.ogg']
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Create file path
    file_path = os.path.join(MUSIC_DIR, file.filename)
    
    # Check if file already exists
    service = MusicFileService(db)
    existing = service.get_music_file_by_path(file_path)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"File '{file.filename}' already exists in database"
        )
    
    # Save file to disk
    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Get file size
    file_size = os.path.getsize(file_path)
    
    # Parse tags
    tag_list = []
    if tags:
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
    
    # Create database record
    try:
        music_file = service.create_music_file(
            filename=file.filename,
            file_path=file_path,
            file_size=file_size,
            format=file_ext[1:],  # Remove dot
            category_id=category_id,
            tags=tag_list
        )
        
        return {
            "success": True,
            "message": "Music file uploaded successfully",
            "music_file": music_file.to_dict()
        }
    except Exception as e:
        # Delete file if database insert fails
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to create database record: {str(e)}")


@router.post("/bulk-upload")
async def bulk_upload_music_files(
    files: List[UploadFile] = File(...),
    category_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload multiple music files"""
    service = MusicFileService(db)
    allowed_extensions = ['.mp3', '.aac', '.m4a', '.wav', '.flac', '.ogg']
    
    results = {
        "success": [],
        "failed": [],
        "skipped": []
    }
    
    for file in files:
        if not file.filename:
            results["failed"].append({"filename": "unknown", "error": "Empty filename"})
            continue
        
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        # Validate extension
        if file_ext not in allowed_extensions:
            results["skipped"].append({
                "filename": file.filename,
                "reason": f"Invalid file type: {file_ext}"
            })
            continue
        
        file_path = os.path.join(MUSIC_DIR, file.filename)
        
        # Check if exists
        if service.get_music_file_by_path(file_path):
            results["skipped"].append({
                "filename": file.filename,
                "reason": "File already exists"
            })
            continue
        
        # Save file
        try:
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            
            file_size = os.path.getsize(file_path)
            
            # Create record
            music_file = service.create_music_file(
                filename=file.filename,
                file_path=file_path,
                file_size=file_size,
                format=file_ext[1:],
                category_id=category_id
            )
            
            results["success"].append({
                "filename": file.filename,
                "id": music_file.id,
                "size": file_size
            })
            
        except Exception as e:
            # Clean up file if failed
            if os.path.exists(file_path):
                os.remove(file_path)
            
            results["failed"].append({
                "filename": file.filename,
                "error": str(e)
            })
    
    return {
        "total": len(files),
        "success_count": len(results["success"]),
        "failed_count": len(results["failed"]),
        "skipped_count": len(results["skipped"]),
        "results": results
    }


@router.post("/import-directory")
async def import_from_directory(
    directory: str = Form(...),
    category_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """Import all music files from a directory"""
    service = MusicFileService(db)
    
    if not os.path.exists(directory):
        raise HTTPException(status_code=404, detail="Directory not found")
    
    if not os.path.isdir(directory):
        raise HTTPException(status_code=400, detail="Path is not a directory")
    
    imported_count = service.bulk_import_from_directory(directory, category_id)
    
    return {
        "success": True,
        "message": f"Imported {imported_count} music files",
        "imported_count": imported_count
    }


@router.put("/{music_file_id}")
async def update_music_file(
    music_file_id: int,
    music_file_data: MusicFileUpdate,
    db: Session = Depends(get_db)
):
    """Update music file metadata"""
    service = MusicFileService(db)
    
    music_file = service.update_music_file(
        music_file_id=music_file_id,
        filename=music_file_data.filename,
        category_id=music_file_data.category_id,
        tags=music_file_data.tags
    )
    
    if not music_file:
        raise HTTPException(status_code=404, detail="Music file not found")
    
    return {
        "success": True,
        "message": "Music file updated successfully",
        "music_file": music_file.to_dict()
    }


@router.delete("/{music_file_id}")
async def delete_music_file(
    music_file_id: int,
    delete_file: bool = True,
    db: Session = Depends(get_db)
):
    """Delete music file"""
    service = MusicFileService(db)
    
    success = service.delete_music_file(music_file_id, delete_file)
    
    if not success:
        raise HTTPException(status_code=404, detail="Music file not found")
    
    return {
        "success": True,
        "message": "Music file deleted successfully"
    }
