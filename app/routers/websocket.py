"""
WebSocket router for real-time monitoring.
"""
import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.database import SessionLocal
from app.models.live_session import LiveSession
from app.services.ffmpeg_service import ffmpeg_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["WebSocket"])

# Store active connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

@router.websocket("/monitoring")
async def monitoring_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Fetch active sessions data
            db = SessionLocal()
            try:
                active_sessions = db.query(LiveSession).filter(
                    LiveSession.status.in_(['running', 'recovering'])
                ).all()
                
                status_data = []
                for session in active_sessions:
                    data = session.to_dict()
                    
                    # Add real-time stats from FFmpeg log if available
                    # For now, we manually add some stats or extracted from log
                    stats = {
                        'bitrate': 'N/A',
                        'fps': 'N/A',
                        'speed': 'N/A'
                    }
                    
                    log_content = ffmpeg_service.get_log_content(session.id, lines=5)
                    if log_content:
                        # Simple parser for FFmpeg status lines
                        # frame=  123 fps= 30 q=28.0 size=    1024kB time=00:00:04.10 bitrate=2048.0kbits/s speed=1.0x
                        if 'bitrate=' in log_content:
                            try:
                                parts = log_content.split('bitrate=')[-1].split()
                                stats['bitrate'] = parts[0]
                            except: pass
                        if 'fps=' in log_content:
                            try:
                                parts = log_content.split('fps=')[-1].split()
                                stats['fps'] = parts[0]
                            except: pass
                        if 'speed=' in log_content:
                            try:
                                parts = log_content.split('speed=')[-1].split()
                                stats['speed'] = parts[0]
                            except: pass
                    
                    data['stats'] = stats
                    status_data.append(data)
                
                await websocket.send_text(json.dumps({
                    'type': 'status_update',
                    'sessions': status_data
                }))
            finally:
                db.close()
                
            # Update every 2 seconds
            await asyncio.sleep(2)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
