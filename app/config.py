from dotenv import load_dotenv
import os

load_dotenv()

YOUTUBE_STREAM_KEY = os.getenv("YOUTUBE_STREAM_KEY")
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
# Determine absolute path to data.db to avoid CWD issues
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # app/
PROJECT_ROOT = os.path.dirname(BASE_DIR) # project root

# Default to data.db in project root
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_ENV_FILE")

# Stream limits
MAX_CONCURRENT_STREAMS = int(os.getenv("MAX_CONCURRENT_STREAMS", "10"))

# FFmpeg Settings
FFMPEG_PRESET = os.getenv("FFMPEG_PRESET", "veryfast")
FFMPEG_MAXRATE = os.getenv("FFMPEG_MAXRATE", "3000k")
FFMPEG_BUFSIZE = os.getenv("FFMPEG_BUFSIZE", "6000k")
FFMPEG_GOP = os.getenv("FFMPEG_GOP", "50")

# Storage
VIDEO_STORAGE_PATH = os.getenv("VIDEO_STORAGE_PATH", "videos")
