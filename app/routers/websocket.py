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
                    
                    
                    # Add process status (restart count)
                    process_status = ffmpeg_service.get_process_status(session.id)
                    if process_status:
                        data['restart_count'] = process_status.get('retry_count', 0)
                        data['max_retries'] = process_status.get('max_retries', 5)
                    else:
                        data['restart_count'] = 0

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
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@router.websocket("/logs/{session_id}")
async def stream_logs_ws(websocket: WebSocket, session_id: int):
    """
    WebSocket endpoint to stream FFmpeg logs in real-time.
    Acts like 'tail -f'.
    """
    await manager.connect(websocket)
    try:
        # Get session to find log file
        db = SessionLocal()
        session = db.query(LiveSession).filter(LiveSession.id == session_id).first()
        db.close()

        if not session:
            await websocket.send_text("Session not found")
            await websocket.close()
            return
            
        # Get log file path from service
        # If active, get from registry. If not, try to find file.
        log_file = None
        if session_id in ffmpeg_service.active_processes:
            log_file = ffmpeg_service.active_processes[session_id]['log_file']
        else:
            # Try to find latest log file for this session
            import os
            log_dir = ffmpeg_service.log_dir
            files = sorted([f for f in os.listdir(log_dir) if f.startswith(f"session_{session_id}_")])
            if files:
                log_file = os.path.join(log_dir, files[-1])
        
        if not log_file or not os.path.exists(log_file):
            await websocket.send_text("Log file not found")
            await websocket.close()
            return

        # Tail the file
        with open(log_file, 'r') as f:
            # Go to end of file for new logs, or read last N lines?
            # Let's read last 50 lines first
            lines = f.readlines()
            for line in lines[-50:]:
                await websocket.send_text(line)
            
            # Now tail
            import time
            f.seek(0, 2) # Go to end
            
            while True:
                line = f.readline()
                if line:
                    await websocket.send_text(line)
                else:
                    await asyncio.sleep(0.1)
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Log WebSocket error: {e}")
        try:
            await websocket.send_text(f"Error: {str(e)}")
            manager.disconnect(websocket)
        except:
            pass
