"""
Service untuk mengelola music files.
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import List, Optional, Tuple
from datetime import datetime
import os
import subprocess
import json

from app.models.music_file import MusicFile
from app.models.category import Category


class MusicFileService:
    """Service untuk CRUD operations pada music files"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_music_file(
        self,
        filename: str,
        file_path: str,
        file_size: int,
        format: str,
        category_id: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> MusicFile:
        """
        Create new music file record.
        
        Args:
            filename: File name
            file_path: Full path to file
            file_size: File size in bytes
            format: File format (mp3, aac, etc.)
            category_id: Optional category ID
            tags: Optional list of tags
            
        Returns:
            Created MusicFile object
        """
        # Extract duration using ffprobe
        duration = self.extract_duration(file_path)
        
        music_file = MusicFile(
            filename=filename,
            file_path=file_path,
            file_size=file_size,
            format=format,
            duration=duration,
            category_id=category_id,
            tags=tags or []
        )
        
        self.db.add(music_file)
        self.db.commit()
        self.db.refresh(music_file)
        
        return music_file
    
    def get_all_music_files(
        self,
        page: int = 1,
        limit: int = 50,
        search: Optional[str] = None,
        category_id: Optional[int] = None,
        format: Optional[str] = None,
        sort: str = "filename",
        order: str = "asc"
    ) -> Tuple[List[MusicFile], int]:
        """
        Get all music files with pagination and filters.
        
        Args:
            page: Page number (1-indexed)
            limit: Items per page
            search: Search term for filename
            category_id: Filter by category
            format: Filter by format
            sort: Sort field (filename, uploaded_at, duration, file_size)
            order: Sort order (asc, desc)
            
        Returns:
            Tuple of (list of MusicFile, total count)
        """
        query = self.db.query(MusicFile)
        
        # Apply filters
        if search:
            query = query.filter(
                or_(
                    MusicFile.filename.ilike(f"%{search}%"),
                    MusicFile.tags.contains([search])
                )
            )
        
        if category_id is not None:
            query = query.filter(MusicFile.category_id == category_id)
        
        if format:
            query = query.filter(MusicFile.format == format)
        
        # Get total count before pagination
        total = query.count()
        
        # Apply sorting
        sort_column = getattr(MusicFile, sort, MusicFile.filename)
        if order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
        
        # Apply pagination
        offset = (page - 1) * limit
        music_files = query.offset(offset).limit(limit).all()
        
        return music_files, total
    
    def get_music_file(self, music_file_id: int) -> Optional[MusicFile]:
        """Get music file by ID"""
        return self.db.query(MusicFile).filter(MusicFile.id == music_file_id).first()
    
    def get_music_file_by_path(self, file_path: str) -> Optional[MusicFile]:
        """Get music file by path"""
        return self.db.query(MusicFile).filter(MusicFile.file_path == file_path).first()
    
    def update_music_file(
        self,
        music_file_id: int,
        filename: Optional[str] = None,
        category_id: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> Optional[MusicFile]:
        """
        Update music file metadata.
        
        Args:
            music_file_id: Music file ID
            filename: New filename (optional)
            category_id: New category ID (optional)
            tags: New tags (optional)
            
        Returns:
            Updated MusicFile object or None if not found
        """
        music_file = self.get_music_file(music_file_id)
        
        if not music_file:
            return None
        
        if filename is not None:
            music_file.filename = filename
        if category_id is not None:
            music_file.category_id = category_id
        if tags is not None:
            music_file.tags = tags
        
        self.db.commit()
        self.db.refresh(music_file)
        
        return music_file
    
    def delete_music_file(self, music_file_id: int, delete_file: bool = True) -> bool:
        """
        Delete music file.
        
        Args:
            music_file_id: Music file ID
            delete_file: Whether to delete physical file
            
        Returns:
            True if deleted, False if not found
        """
        music_file = self.get_music_file(music_file_id)
        
        if not music_file:
            return False
        
        # Delete physical file if requested
        if delete_file and os.path.exists(music_file.file_path):
            try:
                os.remove(music_file.file_path)
            except Exception as e:
                print(f"Error deleting file {music_file.file_path}: {e}")
        
        self.db.delete(music_file)
        self.db.commit()
        
        return True
    
    def search_music_files(self, search_term: str, limit: int = 50) -> List[MusicFile]:
        """
        Search music files by filename or tags.
        
        Args:
            search_term: Search term
            limit: Maximum results
            
        Returns:
            List of matching MusicFile objects
        """
        return self.db.query(MusicFile).filter(
            or_(
                MusicFile.filename.ilike(f"%{search_term}%"),
                MusicFile.tags.contains([search_term])
            )
        ).limit(limit).all()
    
    def update_last_used(self, music_file_id: int):
        """Update last_used timestamp"""
        music_file = self.get_music_file(music_file_id)
        if music_file:
            music_file.last_used = datetime.utcnow()
            self.db.commit()
    
    def extract_duration(self, file_path: str) -> Optional[float]:
        """
        Extract audio duration using ffprobe.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Duration in seconds or None if extraction fails
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                duration = float(data.get('format', {}).get('duration', 0))
                return duration if duration > 0 else None
            
        except Exception as e:
            print(f"Error extracting duration from {file_path}: {e}")
        
        return None
    
    def get_formats(self) -> List[str]:
        """Get list of unique formats in database"""
        formats = self.db.query(MusicFile.format).distinct().all()
        return [f[0] for f in formats if f[0]]
    
    def bulk_import_from_directory(self, directory: str, category_id: Optional[int] = None) -> int:
        """
        Bulk import music files from directory.
        
        Args:
            directory: Directory path
            category_id: Optional category ID for all files
            
        Returns:
            Number of files imported
        """
        if not os.path.exists(directory):
            return 0
        
        imported_count = 0
        supported_formats = ['.mp3', '.aac', '.m4a', '.wav', '.flac', '.ogg']
        
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            
            if not os.path.isfile(file_path):
                continue
            
            file_ext = os.path.splitext(filename)[1].lower()
            
            if file_ext not in supported_formats:
                continue
            
            # Check if already exists
            if self.get_music_file_by_path(file_path):
                continue
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            # Create record
            try:
                self.create_music_file(
                    filename=filename,
                    file_path=file_path,
                    file_size=file_size,
                    format=file_ext[1:],  # Remove dot
                    category_id=category_id
                )
                imported_count += 1
            except Exception as e:
                print(f"Error importing {filename}: {e}")
        
        return imported_count
