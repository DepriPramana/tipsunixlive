"""
YouTube API router untuk managing multiple live broadcasts.
"""
import json
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.database import SessionLocal
from app.services.youtube_api_service import youtube_api, YouTubeAPIService
from app.services.youtube_broadcast_service import YouTubeBroadcastService
from app.models.stream_key import StreamKey
from app.models.youtube_account import YouTubeAccount
import os
import shutil
from typing import Dict, Any

router = APIRouter(prefix="/youtube", tags=["YouTube API"])
logger = logging.getLogger(__name__)


def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_youtube_service(db: Session = Depends(get_db)):
    """Dependency to get YouTube API service instance."""
    return youtube_api # Assuming youtube_api is a global instance or managed elsewhere


class CreateLiveSetupRequest(BaseModel):
    """Request model untuk create live setup"""
    broadcast_title: str
    stream_name: str
    description: Optional[str] = ""
    scheduled_start_time: Optional[str] = None  # ISO format
    privacy_status: Optional[str] = "public"
    account_id: Optional[int] = None
    resolution: Optional[str] = "1080p"
    frame_rate: Optional[str] = "30fps"
    latency_mode: Optional[str] = "normal"
    enable_dvr: Optional[bool] = True
    made_for_kids: Optional[bool] = False
    category_id: Optional[str] = "24"
    enable_embed: Optional[bool] = True
    enable_chat: Optional[bool] = True
    tags: Optional[str] = None
    language: Optional[str] = "id"
    license: Optional[str] = "youtube"
    auto_start: Optional[bool] = True
    auto_stop: Optional[bool] = True
    playlist_id: Optional[str] = None


class CreateMultipleLivesRequest(BaseModel):
    """Request model untuk create multiple lives"""
    setups: List[CreateLiveSetupRequest]
    account_id: Optional[int] = None


@router.post("/create-live-setup")
def create_live_setup(
    broadcast_title: str = Form(...),
    stream_name: str = Form(...),
    description: Optional[str] = Form(""),
    scheduled_start_time: Optional[str] = Form(None),
    privacy_status: Optional[str] = Form("public"),
    account_id: Optional[int] = Form(None),
    resolution: Optional[str] = Form("1080p"),
    frame_rate: Optional[str] = Form("30fps"),
    latency_mode: Optional[str] = Form("normal"),
    enable_dvr: Optional[bool] = Form(True),
    made_for_kids: Optional[bool] = Form(False),
    category_id: Optional[str] = Form("24"),
    enable_embed: Optional[bool] = Form(True),
    enable_chat: Optional[bool] = Form(True),
    tags: Optional[str] = Form(None),
    language: Optional[str] = Form("id"),
    license: Optional[str] = Form("youtube"),
    auto_start: Optional[bool] = Form(True),
    auto_stop: Optional[bool] = Form(True),
    playlist_id: Optional[str] = Form(None),
    thumbnail: Optional[UploadFile] = File(None),
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
    if scheduled_start_time:
        try:
            scheduled_time = datetime.fromisoformat(scheduled_start_time)
        except ValueError:
            raise HTTPException(400, "Invalid datetime format. Use ISO format")
    
    # Authenticate with specific account if provided
    if account_id:
        account = db.query(YouTubeAccount).filter(YouTubeAccount.id == account_id).first()
        if not account:
            raise HTTPException(404, f"YouTube Account {account_id} not found")
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
            title=broadcast_title,
            description=description,
            scheduled_start_time=scheduled_time,
            privacy_status=privacy_status,
            resolution=resolution,
            frame_rate=frame_rate,
            latency_mode=latency_mode,
            enable_dvr=enable_dvr,
            made_for_kids=made_for_kids,
            category_id=category_id,
            enable_embed=enable_embed,
            enable_chat=enable_chat,
            tags=tags,
            language=language,
            license=license,
            auto_start=auto_start,
            auto_stop=auto_stop,
            playlist_id=playlist_id
        )
        
        # Handle Thumbnail if provided
        if result and result.get('success') and thumbnail:
            broadcast_id = result.get('broadcast_id')
            
            # Save thumbnail temporarily
            temp_dir = "temp/thumbnails"
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, f"{broadcast_id}_{thumbnail.filename}")
            
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(thumbnail.file, buffer)
            
            # Set thumbnail via API
            thumb_success = youtube_api.set_thumbnail(broadcast_id, temp_path)
            
            if thumb_success:
                result['thumbnail_updated'] = True
                # Update DB record with local reference if needed or just mark as success
                from app.services.youtube_broadcast_service import YouTubeBroadcastService
                broadcast_service = YouTubeBroadcastService(db)
                # In real scenario, we might want to store the URL if YouTube returns it, 
                # but thumbnails().set() doesn't return the URL directly in a simple way.
                # Usually it takes time to process.
            
            # Cleanup temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        return result
        
    except FileNotFoundError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, f"Error creating live setup: {str(e)}")


@router.post("/create-multiple-lives")
async def create_multiple_lives(
    background_tasks: BackgroundTasks,
    setups: str = Form(...),
    account_id: Optional[int] = Form(None),
    thumbnail: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    youtube_api: YouTubeAPIService = Depends(get_youtube_service)
):
    """
    Create multiple live setups at once.
    
    Allows creating multiple independent live broadcasts on same channel.
    Each will have its own stream key.
    
    Args:
        setups: JSON string of list of setups
        account_id: YouTube account ID
        thumbnail: Optional thumbnail image for ALL broadcasts
        
    Returns:
        List of created setups
    """
    try:
        # Parse setups JSON
        setups_data = json.loads(setups)
        if not isinstance(setups_data, list):
            raise HTTPException(400, "Setups must be a JSON array of objects.")
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON format for setups")
        
    # Handle Thumbnail
    thumbnail_path = None
    if thumbnail:
        try:
            suffix = Path(thumbnail.filename).suffix
            # Use NamedTemporaryFile to ensure unique name and proper cleanup
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                shutil.copyfileobj(thumbnail.file, tmp)
                thumbnail_path = tmp.name
            background_tasks.add_task(os.unlink, thumbnail_path) # Schedule cleanup
        except Exception as e:
            logger.error(f"Failed to save thumbnail: {e}")
            raise HTTPException(500, f"Failed to save thumbnail: {e}")
    
    # Authenticate with specific account if provided
    if account_id:
        account = db.query(YouTubeAccount).filter(YouTubeAccount.id == account_id).first()
        if not account:
            raise HTTPException(404, f"YouTube Account {account_id} not found")
        youtube_api.authenticate(token_filename=account.token_filename)
    else:
        # Try to find any active account
        account = db.query(YouTubeAccount).filter(YouTubeAccount.is_active == True).first()
        if account:
            youtube_api.authenticate(token_filename=account.token_filename)
        else:
            # Fallback to default
            youtube_api.authenticate() # Authenticate with default credentials

    results = []
    broadcast_service = YouTubeBroadcastService(db) # Initialize broadcast service

    for setup in setups_data:
        scheduled_time = None
        if setup.get('scheduled_start_time'):
            try:
                scheduled_time = datetime.fromisoformat(setup.get('scheduled_start_time'))
            except ValueError:
                logger.error(f"Invalid datetime format for '{setup.get('broadcast_title')}': {setup.get('scheduled_start_time')}")
                results.append({
                    'success': False,
                    'broadcast_title': setup.get('broadcast_title', 'Unknown'),
                    'error': f"Invalid datetime format: {setup.get('scheduled_start_time')}"
                })
                continue # Skip to next setup

        try:
            result = youtube_api.create_complete_live_setup(
                db=db, # Pass db to the service method
                title=setup.get('broadcast_title', 'Untitled Broadcast'),
                description=setup.get('description', ''),
                scheduled_start_time=scheduled_time,
                privacy_status=setup.get('privacy_status', 'public'),
                resolution=setup.get('resolution', '1080p'),
                frame_rate=setup.get('frame_rate', '30fps'),
                latency_mode=setup.get('latency_mode', 'normal'),
                enable_dvr=setup.get('enable_dvr', True),
                made_for_kids=setup.get('made_for_kids', False),
                category_id=setup.get('category_id', '24'),
                enable_embed=setup.get('enable_embed', True),
                enable_chat=setup.get('enable_chat', True),
                tags=setup.get('tags'),
                language=setup.get('language', 'id'),
                license=setup.get('license', 'youtube'),
                auto_start=setup.get('auto_start', True),
                auto_stop=setup.get('auto_stop', True),
                playlist_id=setup.get('playlist_id')
            )
            
            if result and result.get('success'):
                # Set thumbnail if available
                if thumbnail_path:
                    thumb_success = youtube_api.set_thumbnail(result['broadcast_id'], thumbnail_path)
                    if thumb_success:
                        result['thumbnail_updated'] = True
                    else:
                        logger.warning(f"Failed to set thumbnail for broadcast {result['broadcast_id']}")
                        result['thumbnail_updated'] = False
                
                # Save to DB
                broadcast_service.create_broadcast(
                    db=db,
                    broadcast_id=result['broadcast_id'],
                    stream_id=result['stream_id'],
                    stream_key=result['stream_key'],
                    rtmp_url=result['rtmp_url'],
                    ingestion_address=result['ingestion_address'],
                    title=setup.get('broadcast_title', 'Untitled Broadcast'),
                    description=setup.get('description', ''),
                    broadcast_url=result['broadcast_url'],
                    privacy_status=setup.get('privacy_status', 'public'),
                    resolution=setup.get('resolution', '1080p'),
                    frame_rate=setup.get('frame_rate', '30fps'),
                    latency_mode=setup.get('latency_mode', 'normal'),
                    enable_dvr=setup.get('enable_dvr', True),
                    made_for_kids=setup.get('made_for_kids', False),
                    category_id=setup.get('category_id', '24'),
                    thumbnail_url=None, # YouTube API doesn't return URL directly after set
                    enable_embed=setup.get('enable_embed', True),
                    enable_chat=setup.get('enable_chat', True),
                    tags=setup.get('tags'),
                    language=setup.get('language', 'id'),
                    license=setup.get('license', 'youtube'),
                    auto_start=setup.get('auto_start', True),
                    auto_stop=setup.get('auto_stop', True)
                )
                
                result['success'] = True
                results.append(result)
            else:
                results.append({
                    'success': False,
                    'broadcast_title': setup.get('broadcast_title', 'Unknown'),
                    'error': result.get('error', 'Failed to create broadcast')
                })
                
        except Exception as e:
            logger.error(f"Error creating live setup for '{setup.get('broadcast_title', 'Unknown')}': {e}")
            results.append({
                'success': False,
                'broadcast_title': setup.get('broadcast_title', 'Unknown'),
                'error': str(e)
            })
                
    return {
        "total_requested": len(setups_data),
        "total_created": len([r for r in results if r.get('success')]),
        "total_failed": len(setups_data) - len([r for r in results if r.get('success')]),
        "results": results
    }


@router.get("/playlists")
async def list_playlists(
    youtube_api: YouTubeAPIService = Depends(get_youtube_service)
):
    """List user's playlists."""
    try:
        playlists = youtube_api.list_playlists()
        return playlists
    except Exception as e:
        logger.error(f"Error fetching playlists: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
