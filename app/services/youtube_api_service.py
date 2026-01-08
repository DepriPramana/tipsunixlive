"""
YouTube Data API v3 Integration Service.
Handles OAuth2 authentication, live broadcast creation, and stream management.
"""
import os
import pickle
import logging
from typing import Optional, Dict, Tuple, List
from datetime import datetime, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# YouTube API scopes
SCOPES = [
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/youtube.force-ssl'
]

# Paths
DEFAULT_TOKEN_FILE = 'youtube_token.pickle'
CREDENTIALS_FILE = 'client_secrets.json'


class YouTubeAPIService:
    """Service untuk mengelola YouTube Data API v3"""
    
    def __init__(self):
        self.credentials: Optional[Credentials] = None
        self.youtube = None
    
    def authenticate(self, token_filename: str = DEFAULT_TOKEN_FILE) -> bool:
        """
        Authenticate dengan YouTube API menggunakan OAuth2.
        
        Args:
            token_filename: Nama file pickle untuk menyimpan token (untuk multi-channel)
            
        Returns:
            True jika berhasil authenticate, False jika gagal
        """
        logger.info(f"🔐 Starting YouTube API authentication (token: {token_filename})...")
        
        # Load credentials dari token file jika ada
        if os.path.exists(token_filename):
            logger.info(f"Loading existing credentials from {token_filename}...")
            with open(token_filename, 'rb') as token:
                self.credentials = pickle.load(token)
        
        # Refresh atau create new credentials
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                logger.info("Refreshing expired credentials...")
                try:
                    self.credentials.refresh(Request())
                except Exception as e:
                    logger.error(f"Failed to refresh credentials: {e}")
                    self.credentials = None
            
            if not self.credentials:
                # Check for both plural and singular filenames
                creds_file = CREDENTIALS_FILE
                if not os.path.exists(creds_file) and os.path.exists('client_secret.json'):
                    creds_file = 'client_secret.json'
                
                if not os.path.exists(creds_file):
                    logger.error(f"❌ {CREDENTIALS_FILE} not found!")
                    logger.error("Please download OAuth2 credentials from Google Cloud Console")
                    return False
                
                logger.info(f"Starting OAuth2 flow using {creds_file}...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    creds_file, SCOPES
                )
                self.credentials = flow.run_local_server(port=8080)
            
            # Save credentials
            with open(token_filename, 'wb') as token:
                pickle.dump(self.credentials, token)
            logger.info(f"✅ Credentials saved to {token_filename}")
        
        # Build YouTube service
        try:
            self.youtube = build('youtube', 'v3', credentials=self.credentials)
            logger.info("✅ YouTube API service initialized")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to build YouTube service: {e}")
            return False
            
    def get_channel_info(self) -> Optional[Dict]:
        """
        Get current channel info.
        """
        if not self.youtube:
            return None
            
        try:
            request = self.youtube.channels().list(
                part="snippet,contentDetails,statistics",
                mine=True
            )
            response = request.execute()
            
            if 'items' in response and len(response['items']) > 0:
                channel = response['items'][0]
                return {
                    'id': channel['id'],
                    'title': channel['snippet']['title'],
                    'custom_url': channel['snippet'].get('customUrl'),
                    'thumbnail': channel['snippet']['thumbnails']['default']['url']
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get channel info: {e}")
            return None
    
    def create_live_broadcast(
        self,
        title: str,
        description: str = "",
        scheduled_start_time: Optional[datetime] = None,
        privacy_status: str = "public",
        enable_dvr: bool = True,
        made_for_kids: bool = False,
        category_id: str = "24",  # Default: Entertainment
        enable_embed: bool = True,
        enable_chat: bool = True,
        tags: Optional[str] = None,
        language: str = "id",
        license: str = "youtube",  # youtube, creativeCommon
        auto_start: bool = True,
        auto_stop: bool = True
    ) -> Optional[Dict]:
        """
        Create live broadcast di YouTube.
        
        Args:
            title: Judul broadcast
            description: Deskripsi broadcast
            scheduled_start_time: Waktu mulai (None untuk now)
            privacy_status: public, unlisted, atau private
            enable_dvr: Aktifkan DVR
            made_for_kids: Ditandai untuk anak-anak
            category_id: YouTube category ID
            enable_embed: Izinkan embedding
            enable_chat: Aktifkan live chat
            tags: Tags
            language: Language
            license: License
            auto_start: Auto Start
            auto_stop: Auto Stop
            
        Returns:
            Broadcast object atau None jika gagal
        """
        if not self.youtube:
            logger.error("YouTube service not initialized")
            return None
        
        logger.info(f"📺 Creating live broadcast: {title}")
        
        # Default to now + 5 minutes
        if not scheduled_start_time:
            scheduled_start_time = datetime.utcnow() + timedelta(minutes=5)
        
        # Format ISO 8601
        start_time_iso = scheduled_start_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        
        try:
            broadcast_request = self.youtube.liveBroadcasts().insert(
                part="snippet,status,contentDetails",
                body={
                    "snippet": {
                        "title": title,
                        "description": description,
                        "scheduledStartTime": start_time_iso,
                        "categoryId": category_id,
                        # Attempt to set video metadata on broadcast creation
                        "tags": [t.strip() for t in tags.split(',')] if tags else [],
                        "defaultLanguage": language,
                        "defaultAudioLanguage": language
                    },
                    "status": {
                        "privacyStatus": privacy_status,
                        "selfDeclaredMadeForKids": made_for_kids,
                        "license": license
                    },
                    "contentDetails": {
                        "enableAutoStart": auto_start,
                        "enableAutoStop": auto_stop,
                        "enableDvr": enable_dvr,
                        "enableContentEncryption": False,
                        "enableEmbed": enable_embed,
                        "recordFromStart": True,
                        "startWithSlate": False,
                        "enableLiveChat": enable_chat,
                        "monitorStream": {
                            "enableMonitorStream": True,
                            "broadcastStreamDelayMs": 0
                        }
                    }
                }
            )
            
            broadcast = broadcast_request.execute()
            
            logger.info(f"✅ Broadcast created: {broadcast['id']}")
            return broadcast
            
        except HttpError as e:
            logger.error(f"❌ Failed to create broadcast: {e}")
            return None
    
    def create_live_stream(
        self,
        title: str,
        resolution: str = "1080p",
        frame_rate: str = "30fps",
        latency_mode: str = "normal"  # normal, low, ultraLow
    ) -> Optional[Dict]:
        """
        Create live stream di YouTube.
        
        Args:
            title: Judul stream
            resolution: 1080p, 720p, 480p, 360p, 240p
            frame_rate: 30fps atau 60fps
            latency_mode: normal, low, atau ultraLow
            
        Returns:
            Stream object atau None jika gagal
        """
        if not self.youtube:
            logger.error("YouTube service not initialized")
            return None
        
        logger.info(f"🎥 Creating live stream: {title} (Latency: {latency_mode})")
        
        try:
            stream_request = self.youtube.liveStreams().insert(
                part="snippet,cdn,status",
                body={
                    "snippet": {
                        "title": title,
                        "description": f"Live stream for {title}"
                    },
                    "cdn": {
                        "frameRate": frame_rate,
                        "ingestionType": "rtmp",
                        "resolution": resolution,
                        "latencyPreference": latency_mode
                    },
                    "status": {
                        "streamStatus": "active"
                    },
                    "contentDetails": {
                        "isReusable": True
                    }
                }
            )
            
            stream = stream_request.execute()
            
            logger.info(f"✅ Stream created: {stream['id']}")
            return stream
            
        except HttpError as e:
            logger.error(f"❌ Failed to create stream: {e}")
            return None

    def bind_broadcast_to_stream(
        self,
        broadcast_id: str,
        stream_id: str
    ) -> bool:
        """
        Bind broadcast ke stream.
        
        Args:
            broadcast_id: ID broadcast
            stream_id: ID stream
            
        Returns:
            True jika berhasil, False jika gagal
        """
        if not self.youtube:
            logger.error("YouTube service not initialized")
            return False
        
        logger.info(f"🔗 Binding broadcast {broadcast_id} to stream {stream_id}")
        
        try:
            bind_request = self.youtube.liveBroadcasts().bind(
                part="id,snippet,status",
                id=broadcast_id,
                streamId=stream_id
            )
            
            response = bind_request.execute()
            
            logger.info(f"✅ Broadcast bound to stream successfully")
            logger.info(f"   Broadcast: {response['snippet']['title']}")
            logger.info(f"   Status: {response['status']['lifeCycleStatus']}")
            
            return True
            
        except HttpError as e:
            logger.error(f"❌ Failed to bind broadcast to stream: {e}")
            return False
    
    def get_stream_key(self, stream_id: str) -> Optional[str]:
        """
        Get stream key dari stream.
        
        Args:
            stream_id: ID stream
            
        Returns:
            Stream key atau None jika gagal
        """
        if not self.youtube:
            logger.error("YouTube service not initialized")
            return None
        
        logger.info(f"🔑 Getting stream key for stream {stream_id}")
        
        try:
            stream_request = self.youtube.liveStreams().list(
                part="cdn",
                id=stream_id
            )
            
            response = stream_request.execute()
            
            if 'items' in response and len(response['items']) > 0:
                stream = response['items'][0]
                stream_name = stream['cdn']['ingestionInfo']['streamName']
                
                logger.info(f"✅ Stream key retrieved")
                logger.info(f"   Stream Name: {stream_name}")
                
                return stream_name
            else:
                logger.error("Stream not found")
                return None
                
        except HttpError as e:
            logger.error(f"❌ Failed to get stream key: {e}")
            return None
    
    def create_complete_live_setup(
        self,
        title: str,
        description: str = "",
        scheduled_start_time: Optional[datetime] = None,
        privacy_status: str = "public",
        resolution: str = "1080p",
        frame_rate: str = "30fps",
        latency_mode: str = "normal",
        enable_dvr: bool = True,
        made_for_kids: bool = False,
        category_id: str = "24",
        enable_embed: bool = True,
        enable_chat: bool = True,
        tags: Optional[str] = None,
        language: str = "id",
        license: str = "youtube",
        auto_start: bool = True,
        auto_stop: bool = True,
        playlist_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Create complete live setup: broadcast + stream + bind.
        
        Args:
            title: Judul broadcast/stream
            description: Deskripsi
            scheduled_start_time: Waktu mulai
            privacy_status: public, unlisted, private
            resolution: 1080p, 720p, etc
            frame_rate: 30fps atau 60fps
            latency_mode: normal, low, ultraLow
            enable_dvr: Aktifkan DVR
            made_for_kids: MenDeclared Made for Kids
            category_id: YouTube category ID
            enable_embed: Izinkan embedding
            enable_chat: Aktifkan live chat
            tags: Tags
            language: Language
            license: License
            auto_start: Auto Start
            auto_stop: Auto Stop
            playlist_id: Optional Playlist ID to add video to
            
        Returns:
            Dictionary berisi broadcast, stream, dan stream_key
        """
        logger.info("="*60)
        logger.info("🚀 Creating complete YouTube Live setup")
        logger.info("="*60)
        
        # Step 1: Authenticate
        if not self.youtube:
            if not self.authenticate():
                return None
        
        # Step 2: Create broadcast
        broadcast = self.create_live_broadcast(
            title=title,
            description=description,
            scheduled_start_time=scheduled_start_time,
            privacy_status=privacy_status,
            enable_dvr=enable_dvr,
            made_for_kids=made_for_kids,
            category_id=category_id,
            enable_embed=enable_embed,
            enable_chat=enable_chat,
            tags=tags,
            language=language,
            license=license,
            auto_start=auto_start,
            auto_stop=auto_stop
        )
        
        if not broadcast:
            return None
        
        # Step 3: Create stream
        stream = self.create_live_stream(
            title=f"Stream for {title}",
            resolution=resolution,
            frame_rate=frame_rate,
            latency_mode=latency_mode
        )
        
        if not stream:
            return None
        
        # Step 4: Bind broadcast to stream
        success = self.bind_broadcast_to_stream(
            broadcast_id=broadcast['id'],
            stream_id=stream['id']
        )
        
        if not success:
            return None
        
        # Step 5: Get stream key
        stream_key = self.get_stream_key(stream['id'])
        
        if not stream_key:
            return None
        
        result = {
            'broadcast_id': broadcast['id'],
            'broadcast_title': broadcast['snippet']['title'],
            'broadcast_url': f"https://www.youtube.com/watch?v={broadcast['id']}",
            'stream_id': stream['id'],
            'stream_key': stream_key,
            'ingestion_address': stream['cdn']['ingestionInfo']['ingestionAddress'],
            'rtmp_url': f"{stream['cdn']['ingestionInfo']['ingestionAddress']}/{stream_key}",
            'status': broadcast['status']['lifeCycleStatus']
        }
        
        logger.info("="*60)
        logger.info("✅ Complete YouTube Live setup created successfully!")
        logger.info("="*60)
        logger.info(f"Broadcast ID: {result['broadcast_id']}")
        logger.info(f"Broadcast URL: {result['broadcast_url']}")
        logger.info(f"Stream Key: {result['stream_key']}")
        logger.info(f"RTMP URL: {result['rtmp_url']}")
        logger.info("="*60)

        # Step 6: Add to Playlist if provided
        if playlist_id:
            self.add_video_to_playlist(playlist_id, broadcast['id'])
        
        return result
    
    def list_live_broadcasts(self, max_results: int = 10) -> list:
        """
        List semua live broadcasts.
        
        Args:
            max_results: Maximum jumlah results
            
        Returns:
            List of broadcasts
        """
        if not self.youtube:
            if not self.authenticate():
                return []
        
        try:
            request = self.youtube.liveBroadcasts().list(
                part="snippet,status",
                mine=True,
                maxResults=max_results
            )
            
            response = request.execute()
            return response.get('items', [])
            
        except HttpError as e:
            logger.error(f"Failed to list broadcasts: {e}")
            return []
    
    def delete_broadcast(self, broadcast_id: str) -> bool:
        """
        Delete broadcast.
        
        Args:
            broadcast_id: ID broadcast yang akan dihapus
            
        Returns:
            True jika berhasil
        """
        if not self.youtube:
            return False
        
        try:
            self.youtube.liveBroadcasts().delete(id=broadcast_id).execute()
            logger.info(f"✅ Broadcast {broadcast_id} deleted")
            return True
        except HttpError as e:
            logger.error(f"Failed to delete broadcast: {e}")
            return False


    def set_thumbnail(self, broadcast_id: str, image_path: str) -> bool:
        """
        Set custom thumbnail untuk broadcast.
        
        Args:
            broadcast_id: ID broadcast
            image_path: Path ke file gambar
            
        Returns:
            True jika berhasil
        """
        if not self.youtube:
            return False
            
        logger.info(f"🖼️ Setting thumbnail for broadcast {broadcast_id}: {image_path}")
        
        try:
            from googleapiclient.http import MediaFilePathUpload
            
            # Validasi file
            if not os.path.exists(image_path):
                logger.error(f"Thumbnail file not found: {image_path}")
                return False
                
            self.youtube.thumbnails().set(
                videoId=broadcast_id,
                media_body=MediaFilePathUpload(image_path, chunksize=-1, resumable=True)
            ).execute()
            
            logger.info(f"✅ Thumbnail updated successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to set thumbnail: {e}")
            return False



    def list_playlists(self, mine: bool = True) -> List[Dict]:
        """
        List user's playlists.
        """
        if not self.youtube:
            if not self.authenticate():
                return []
        
        try:
            request = self.youtube.playlists().list(
                part="snippet,contentDetails",
                mine=mine,
                maxResults=50
            )
            response = request.execute()
            return response.get('items', [])
        except HttpError as e:
            logger.error(f"Failed to list playlists: {e}")
            return []

    def add_video_to_playlist(self, playlist_id: str, video_id: str) -> bool:
        """
        Add a video to a playlist.
        """
        if not self.youtube:
            return False
            
        try:
            self.youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video_id
                        }
                    }
                }
            ).execute()
            logger.info(f"✅ Video {video_id} added to playlist {playlist_id}")
            return True
        except HttpError as e:
            logger.error(f"Failed to add video to playlist: {e}")
            return False


# Global instance

youtube_api = YouTubeAPIService()
