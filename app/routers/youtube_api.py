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
from app.models.live_session import LiveSession
from app.models.video import Video
from app.models.playlist import Playlist
from app.services.ffmpeg_service import ffmpeg_service
from app.services.live_scheduler_service import live_scheduler
from app.services.playlist_service import PlaylistService
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
    license: str = "youtube"
    playlist_id: Optional[str] = None  # YouTube Playlist ID (add to playlist)
    auto_start: bool = True
    auto_stop: bool = True
    
    # New fields for Auto-Stream
    source_mode: Optional[str] = None  # 'single' or 'playlist'
    video_id: Optional[int] = None
    source_playlist_id: Optional[int] = None # Local Playlist ID
    loop_playback: bool = True
    timing_mode: str = 'now'  # 'now' or 'later'
    max_duration_hours: Optional[int] = 0
    recurrence: str = 'none'



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
    source_mode: Optional[str] = Form(None),
    video_id: Optional[int] = Form(None),
    source_playlist_id: Optional[int] = Form(None),
    loop_playback: bool = Form(True),
    timing_mode: str = Form('now'),
    max_duration_hours: Optional[int] = Form(0),
    recurrence: str = Form('none'),
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
        
        logger.debug(f"Result received: {result.keys() if result else 'None'}")
        if result and result.get('broadcast_id'):
            try:
                # 1. Save Broadcast to DB
                logger.info("Step 1: Saving Broadcast to DB...")
                broadcast_service = YouTubeBroadcastService(db)
                
                # Extract stream key info from flattened result
                stream_key_value = result.get('stream_key')
                rtmp_url = result.get('rtmp_url')
                broadcast_id = result.get('broadcast_id')
                stream_id = result.get('stream_id')
                
                # Save StreamKey to DB
                logger.info(f"Saving StreamKey: {stream_key_value}")
                stream_key_obj = StreamKey(
                    name=f"YT: {broadcast_title[:20]}",
                    stream_key=stream_key_value,
                    is_active=True
                )
                db.add(stream_key_obj)
                db.commit()
                db.refresh(stream_key_obj)
                logger.info(f"StreamKey Saved. ID: {stream_key_obj.id}")
                
                # Save YouTubeBroadcast
                logger.info("Saving YouTubeBroadcast record...")
                broadcast_service.create_broadcast(
                    broadcast_id=broadcast_id,
                    stream_id=stream_id,
                    stream_key=stream_key_value,
                    rtmp_url=rtmp_url,
                    ingestion_address=rtmp_url,
                    title=broadcast_title,
                    description=description,
                    broadcast_url=f"https://youtu.be/{broadcast_id}",
                    privacy_status=privacy_status,
                    resolution=resolution,
                    frame_rate=frame_rate,
                    scheduled_start_time=scheduled_time,
                    latency_mode=latency_mode,
                    enable_dvr=enable_dvr,
                    made_for_kids=made_for_kids,
                    category_id=category_id,
                    thumbnail_url=None, # Thumbnail is handled separately below or not returned in flat dict
                    enable_embed=enable_embed,
                    enable_chat=enable_chat,
                    tags=tags,
                    language=language,
                    license=license,
                    auto_start=auto_start,
                    auto_stop=auto_stop
                )
                logger.info("YouTubeBroadcast record saved.")
                
                response_data = {
                    "success": True,
                    "broadcast_id": broadcast_id,
                    "stream_key": stream_key_value,
                    "stream_started": False,
                    "scheduled_job_id": None
                }

                # 2. Handle Thumbnail if provided
                if thumbnail:
                    logger.info("Processing thumbnail...")
                    # Save thumbnail temporarily
                    temp_dir = "temp/thumbnails"
                    os.makedirs(temp_dir, exist_ok=True)
                    temp_path = os.path.join(temp_dir, f"{broadcast_id}_{thumbnail.filename}")
                    
                    with open(temp_path, "wb") as buffer:
                        shutil.copyfileobj(thumbnail.file, buffer)
                    
                    # Set thumbnail via API
                    logger.info("Uploading thumbnail to YouTube...")
                    thumb_success = youtube_api.set_thumbnail(broadcast_id, temp_path)
                    
                    if thumb_success:
                        response_data['thumbnail_updated'] = True
                    
                    # Cleanup temp file
                    if os.path.exists(temp_path):
                        os.remove(temp_path)

                # 3. Handle Auto-Stream
                if source_mode:
                    logger.info(f"Processing Auto-Stream. Mode: {source_mode}, Timing: {timing_mode}")
                    try:
                        video_paths_list = []
                        
                        if source_mode == 'single' and video_id:
                            logger.info(f"Fetching video ID: {video_id}")
                            video = db.query(Video).filter(Video.id == video_id).first()
                            if video: 
                                video_paths_list = [video.path]
                                logger.info(f"Found video path: {video.path}")
                            else:
                                logger.warning(f"Video ID {video_id} not found!")
                        
                        elif source_mode == 'playlist' and source_playlist_id:
                            logger.info(f"Fetching playlist ID: {source_playlist_id}")
                            pl_service = PlaylistService(db)
                            video_paths_list = pl_service.get_video_paths(source_playlist_id, shuffle=False)
                            logger.info(f"Found {len(video_paths_list)} videos in playlist.")
                        
                        if video_paths_list:
                            if timing_mode == 'now':
                                logger.info("Timing is NOW. Starting stream...")
                                # Start Immediately
                                from datetime import datetime
                                session = LiveSession(
                                    stream_key_id=stream_key_obj.id,
                                    video_id=video_id if source_mode == 'single' else None,
                                    playlist_id=source_playlist_id if source_mode == 'playlist' else None,
                                    mode=source_mode,
                                    loop=loop_playback,
                                    status='starting',
                                    youtube_id=broadcast_id,
                                    max_duration_hours=max_duration_hours,
                                    start_time=datetime.utcnow()
                                )
                                db.add(session)
                                db.commit()
                                db.refresh(session)
                                logger.info(f"LiveSession created. ID: {session.id}")
                                
                                logger.info("Calling ffmpeg_service.start_stream...")
                                process = ffmpeg_service.start_stream(
                                    session_id=session.id,
                                    video_paths=video_paths_list,
                                    stream_key=stream_key_obj.get_full_key(),
                                    loop=loop_playback,
                                    mode=source_mode
                                )
                                
                                if process:
                                    session.ffmpeg_pid = process.pid
                                    session.status = 'running'
                                    db.commit()
                                    response_data['stream_started'] = True
                                    logger.info("Stream started successfully!")
                                else:
                                    logger.error("ffmpeg_service.start_stream returned None!")
                                
                            elif timing_mode == 'later' and scheduled_time:
                                logger.info(f"Timing is LATER. Scheduling for {scheduled_time}...")
                                # Schedule it
                                scheduled_live = live_scheduler.schedule_live(
                                    db=db,
                                    stream_key_id=stream_key_obj.id,
                                    scheduled_time=scheduled_time,
                                    video_id=video_id,
                                    playlist_id=source_playlist_id,
                                    mode=source_mode,
                                    loop=loop_playback,
                                    recurrence=recurrence,
                                    max_duration_hours=max_duration_hours
                                )
                                response_data['scheduled_job_id'] = scheduled_live.id
                                logger.info(f"Stream scheduled. Job ID: {scheduled_live.id}")

                    except Exception as e:
                        logger.error(f"Failed to auto-start/schedule stream: {e}", exc_info=True)
                        # Don't fail the whole request, just log it
                
                return response_data
            
                return response_data
            
            except Exception as e:
                logger.error(f"CRITICAL ERROR in create_live_setup: {str(e)}", exc_info=True)
                
                # Rollback mechanism: Delete the broadcast from YouTube if DB save failed
                if broadcast_id:
                    logger.warning(f"Rolling back: Deleting orphaned broadcast {broadcast_id} from YouTube...")
                    try:
                        youtube_api.delete_broadcast(broadcast_id)
                        logger.info(f"Rollback successful: Broadcast {broadcast_id} deleted.")
                    except Exception as rb_error:
                        logger.error(f"Rollback failed: Could not delete broadcast {broadcast_id}. Error: {rb_error}")

                # Rollback DB transaction
                db.rollback() 
                raise HTTPException(500, f"Internal Server Error: {str(e)}. (Broadcast rolled back)")
            
        else:
             raise HTTPException(500, "Failed to create broadcast (No result returned)")
        
    except FileNotFoundError as e:
        raise HTTPException(500, str(e))
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(500, f"Error creating live setup: {str(e)}")





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
