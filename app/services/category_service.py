"""
Service untuk mengelola categories.
"""
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.category import Category


class CategoryService:
    """Service untuk CRUD operations pada categories"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_category(
        self,
        name: str,
        description: Optional[str] = None,
        color: str = "#6c757d"
    ) -> Category:
        """
        Create new category.
        
        Args:
            name: Category name
            description: Optional description
            color: Hex color code for UI
            
        Returns:
            Created Category object
        """
        category = Category(
            name=name,
            description=description,
            color=color
        )
        
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        
        return category
    
    def get_all_categories(self) -> List[Category]:
        """Get all categories"""
        return self.db.query(Category).order_by(Category.name).all()
    
    def get_category(self, category_id: int) -> Optional[Category]:
        """Get category by ID"""
        return self.db.query(Category).filter(Category.id == category_id).first()
    
    def get_category_by_name(self, name: str) -> Optional[Category]:
        """Get category by name"""
        return self.db.query(Category).filter(Category.name == name).first()
    
    def update_category(
        self,
        category_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None
    ) -> Optional[Category]:
        """
        Update category.
        
        Args:
            category_id: Category ID
            name: New name (optional)
            description: New description (optional)
            color: New color (optional)
            
        Returns:
            Updated Category object or None if not found
        """
        category = self.get_category(category_id)
        
        if not category:
            return None
        
        if name is not None:
            category.name = name
        if description is not None:
            category.description = description
        if color is not None:
            category.color = color
        
        self.db.commit()
        self.db.refresh(category)
        
        return category
    
    def delete_category(self, category_id: int) -> bool:
        """
        Delete category.
        
        Args:
            category_id: Category ID
            
        Returns:
            True if deleted, False if not found
        """
        category = self.get_category(category_id)
        
        if not category:
            return False
        
        # Set category_id to NULL for all music files in this category
        from app.models.music_file import MusicFile
        self.db.query(MusicFile).filter(
            MusicFile.category_id == category_id
        ).update({"category_id": None})
        
        self.db.delete(category)
        self.db.commit()
        
        return True
    
    def get_music_count(self, category_id: int) -> int:
        """Get count of music files in category"""
        from app.models.music_file import MusicFile
        return self.db.query(MusicFile).filter(
            MusicFile.category_id == category_id
        ).count()
