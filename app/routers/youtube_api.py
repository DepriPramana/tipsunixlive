"""
YouTube API router untuk managing multiple live broadcasts.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.database import SessionLocal
from app.services.youtube_api_service import youtube_api
from app.models.stream_key import StreamKey
from app.models.youtube_account import YouTubeAccount

router = APIRouter(prefix="/youtube", tags=["YouTube API"])


def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class CreateLiveSetupRequest(BaseModel):
    """Request model untuk create live setup"""
    broadcast_title: str
    stream_name: str
    description: Optional[str] = ""
    scheduled_start_time: Optional[str] = None  # ISO format
    privacy_status: Optional[str] = "public"
    account_id: Optional[int] = None


class CreateMultipleLivesRequest(BaseModel):
    """Request model untuk create multiple lives"""
    setups: List[CreateLiveSetupRequest]
    account_id: Optional[int] = None


@router.post("/create-live-setup")
def create_live_setup(
    request: CreateLiveSetupRequest,
    db: Session = Depends(get_db)
):
    """
    Create complete live setup: broadcast + stream + bind + save to DB.
    
    Creates:
    1. YouTube live broadcast
    2. YouTube live stream
    3. Binds broadcast to stream
    4. Saves stream key to database
    
    Args:
        request: CreateLiveSetupRequest
        db: Database session
        
    Returns:
        Complete setup info
    """
    
    # Parse scheduled time if provided
    scheduled_time = None
    if request.scheduled_start_time:
        try:
            scheduled_time = datetime.fromisoformat(request.scheduled_start_time)
        except ValueError:
            raise HTTPException(400, "Invalid datetime format. Use ISO format")
    
    # Authenticate with specific account if provided
    if request.account_id:
        account = db.query(YouTubeAccount).filter(YouTubeAccount.id == request.account_id).first()
        if not account:
            raise HTTPException(404, f"YouTube Account {request.account_id} not found")
        youtube_api.authenticate(token_filename=account.token_filename)
    else:
        # Try to find any active account
        account = db.query(YouTubeAccount).filter(YouTubeAccount.is_active == True).first()
        if account:
            youtube_api.authenticate(token_filename=account.token_filename)
        else:
            # Fallback to default
            youtube_api.authenticate()

    # Create complete setup
    try:
        result = youtube_api.create_complete_live_setup(
            db=db,
            title=request.broadcast_title,
            description=request.description,
            scheduled_start_time=scheduled_time,
            privacy_status=request.privacy_status
        )
        
        return result
        
    except FileNotFoundError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, f"Error creating live setup: {str(e)}")


@router.post("/create-multiple-lives")
def create_multiple_lives(
    request: CreateMultipleLivesRequest,
    db: Session = Depends(get_db)
):
    """
    Create multiple live setups at once.
    
    Allows creating multiple independent live broadcasts on same channel.
    Each will have its own stream key.
    
    Args:
        request: CreateMultipleLivesRequest
        db: Database session
        
    Returns:
        List of created setups
    """
    
    # Prepare setups
    setups = []
    for setup in request.setups:
        scheduled_time = None
        if setup.scheduled_start_time:
            try:
                scheduled_time = datetime.fromisoformat(setup.scheduled_start_time)
            except ValueError:
                raise HTTPException(400, f"Invalid datetime format for '{setup.broadcast_title}'")
        
        setups.append({
            'broadcast_title': setup.broadcast_title,
            'stream_name': setup.stream_name,
            'description': setup.description,
            'scheduled_start_time': scheduled_time,
            'privacy_status': setup.privacy_status
        })
    
    # Authenticate with specific account if provided
    if request.account_id:
        account = db.query(YouTubeAccount).filter(YouTubeAccount.id == request.account_id).first()
        if not account:
            raise HTTPException(404, f"YouTube Account {request.account_id} not found")
        youtube_api.authenticate(token_filename=account.token_filename)
    else:
        # Try to find any active account
        account = db.query(YouTubeAccount).filter(YouTubeAccount.is_active == True).first()
        if account:
            youtube_api.authenticate(token_filename=account.token_filename)
        else:
            youtube_api.authenticate()

    # Create all setups
    try:
        results = []
        
        for setup in setups:
            try:
                result = youtube_api.create_complete_live_setup(
                    db=db,
                    title=setup['broadcast_title'],
                    description=setup['description'],
                    scheduled_start_time=setup['scheduled_start_time'],
                    privacy_status=setup['privacy_status']
                )
                results.append(result)
                
            except Exception as e:
                results.append({
                    'success': False,
                    'broadcast_title': setup['broadcast_title'],
                    'error': str(e)
                })
        
        return {
            'total_requested': len(setups),
            'total_created': len([r for r in results if r.get('success')]),
            'total_failed': len([r for r in results if not r.get('success')]),
            'results': results
        }
        
    except Exception as e:
        raise HTTPException(500, f"Error creating multiple lives: {str(e)}")


@router.get("/broadcasts")
def list_broadcasts(
    status: str = "all",
    max_results: int = 50,
    account_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    List YouTube live broadcasts.
    
    Args:
        status: all, active, completed, upcoming
        max_results: Maximum results (1-50)
        account_id: Specific YouTube account ID
        db: Database session
        
    Returns:
        List of broadcasts
    """
    
    if max_results < 1 or max_results > 50:
        raise HTTPException(400, "max_results must be between 1 and 50")
    
    # Authenticate
    if account_id:
        account = db.query(YouTubeAccount).filter(YouTubeAccount.id == account_id).first()
        if not account:
            raise HTTPException(404, "Account not found")
        youtube_api.authenticate(token_filename=account.token_filename)
    else:
        account = db.query(YouTubeAccount).filter(YouTubeAccount.is_active == True).first()
        if account:
            youtube_api.authenticate(token_filename=account.token_filename)
        else:
            youtube_api.authenticate()

    try:
        broadcasts = youtube_api.list_live_broadcasts(max_results=max_results)
        return {
            'total': len(broadcasts),
            'broadcasts': broadcasts
        }
        
    except Exception as e:
        raise HTTPException(500, f"Error listing broadcasts: {str(e)}")


@router.delete("/broadcast/{broadcast_id}")
def delete_broadcast(
    broadcast_id: str,
    account_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Delete a YouTube broadcast.
    
    Args:
        broadcast_id: Broadcast ID
        account_id: Specific YouTube account ID
        db: Database session
        
    Returns:
        Success message
    """
    
    # Authenticate
    if account_id:
        account = db.query(YouTubeAccount).filter(YouTubeAccount.id == account_id).first()
        if not account:
            raise HTTPException(404, "Account not found")
        youtube_api.authenticate(token_filename=account.token_filename)
    
    try:
        success = youtube_api.delete_broadcast(broadcast_id)
        
        if success:
            return {
                'success': True,
                'broadcast_id': broadcast_id,
                'message': f'Broadcast {broadcast_id} deleted'
            }
        else:
            raise HTTPException(500, "Failed to delete broadcast")
            
    except Exception as e:
        raise HTTPException(500, f"Error deleting broadcast: {str(e)}")


@router.get("/stream-keys")
def list_stream_keys_from_db(db: Session = Depends(get_db)):
    """
    List all stream keys from database.
    
    Args:
        db: Database session
        
    Returns:
        List of stream keys
    """
    
    keys = db.query(StreamKey).order_by(StreamKey.created_at.desc()).all()
    
    return {
        'total': len(keys),
        'stream_keys': [k.to_dict() for k in keys]
    }
