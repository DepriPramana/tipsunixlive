from dotenv import load_dotenv
import os

load_dotenv()

YOUTUBE_STREAM_KEY = os.getenv("YOUTUBE_STREAM_KEY")
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data.db")

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_ENV_FILE")

# Stream limits
MAX_CONCURRENT_STREAMS = int(os.getenv("MAX_CONCURRENT_STREAMS", "10"))
