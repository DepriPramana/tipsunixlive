"""
API Router untuk category management.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List

from app.database import SessionLocal
from app.services.category_service import CategoryService


router = APIRouter(prefix="/categories", tags=["Categories"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#6c757d"


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None


@router.get("/")
async def get_categories(db: Session = Depends(get_db)):
    """Get all categories"""
    service = CategoryService(db)
    categories = service.get_all_categories()
    
    # Add music count to each category
    result = []
    for category in categories:
        cat_dict = category.to_dict()
        cat_dict['music_count'] = service.get_music_count(category.id)
        result.append(cat_dict)
    
    return result


@router.get("/{category_id}")
async def get_category(category_id: int, db: Session = Depends(get_db)):
    """Get category by ID"""
    service = CategoryService(db)
    category = service.get_category(category_id)
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    cat_dict = category.to_dict()
    cat_dict['music_count'] = service.get_music_count(category.id)
    
    return cat_dict


@router.post("/")
async def create_category(
    category_data: CategoryCreate,
    db: Session = Depends(get_db)
):
    """Create new category"""
    service = CategoryService(db)
    
    # Check if category with same name exists
    existing = service.get_category_by_name(category_data.name)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Category '{category_data.name}' already exists"
        )
    
    category = service.create_category(
        name=category_data.name,
        description=category_data.description,
        color=category_data.color
    )
    
    return {
        "success": True,
        "message": "Category created successfully",
        "category": category.to_dict()
    }


@router.put("/{category_id}")
async def update_category(
    category_id: int,
    category_data: CategoryUpdate,
    db: Session = Depends(get_db)
):
    """Update category"""
    service = CategoryService(db)
    
    category = service.update_category(
        category_id=category_id,
        name=category_data.name,
        description=category_data.description,
        color=category_data.color
    )
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    return {
        "success": True,
        "message": "Category updated successfully",
        "category": category.to_dict()
    }


@router.delete("/{category_id}")
async def delete_category(category_id: int, db: Session = Depends(get_db)):
    """Delete category"""
    service = CategoryService(db)
    
    # Check music count
    music_count = service.get_music_count(category_id)
    
    success = service.delete_category(category_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Category not found")
    
    return {
        "success": True,
        "message": f"Category deleted successfully. {music_count} music files moved to uncategorized.",
        "music_count": music_count
    }
