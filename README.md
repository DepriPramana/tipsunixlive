# StreamLive - YouTube Live Streaming System

Sistem live streaming 24/7 untuk YouTube dengan support multiple stream keys dan concurrent streams.

## 🚀 Installation & Deployment

Choose your preferred method to run StreamLive.

### 🐳 Docker (Recommended)

The easiest way to run StreamLive is using Docker Compose.

1.  **Clone Release**
    ```bash
    git clone https://github.com/DepriPramana/streamlive.git
    cd streamlive
    ```

2.  **Configure Environment**
    ```bash
    cp .env.example .env
    # Edit .env and set your configurations (Database, Timezone, etc.)
    ```

3.  **Run with Docker Compose**
    ```bash
    docker-compose up -d
    ```
    
    The server will start at **http://localhost:8000**

---

### 🐧 Linux (Manual Production)

For production deployment on Ubuntu/Debian server without Docker.

**Quick Setup:**
```bash
# 1. Install Dependencies
sudo apt update && sudo apt install -y python3-pip python3-venv ffmpeg git nginx

# 2. Clone & Setup
git clone https://github.com/DepriPramana/streamlive.git
cd streamlive
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
python3 init_db.py
python3 seed_user.py

# 4. Run
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

> 📖 **Full Guide:** Read [DEPLOYMENT_LINUX.md](DEPLOYMENT_LINUX.md) for detailed production setup including Nginx, Systemd services, and Firewall configuration.

---

### 🪟 Windows (Local Development)

Best for development and testing.

1.  **Install Prerequisites**
    - [Python 3.9+](https://www.python.org/downloads/)
    - [FFmpeg](https://ffmpeg.org/download.html) (Add to System PATH)
    - [Git](https://git-scm.com/downloads)

2.  **Setup Project**
    ```powershell
    git clone https://github.com/DepriPramana/streamlive.git
    cd streamlive
    python -m venv venv
    .\venv\Scripts\activate
    pip install -r requirements.txt
    ```

3.  **Configure**
    Copy `.env.example` to `.env` and set `FFMPEG_PATH`:
    ```ini
    FFMPEG_PATH=C:\ffmpeg\bin\ffmpeg.exe
    DATABASE_URL=sqlite:///./data.db
    ```

4.  **Initialize Database**
    ```powershell
    python migrate_stream_keys.py
    python migrate_live_sessions.py
    python migrate_scheduled_lives.py
    python seed_stream_keys.py
    ```

5.  **Run Server**
    ```powershell
    uvicorn app.main:app --reload
    ```

---

## 📋 Features

### ✅ Multiple Stream Keys
- Manage multiple YouTube stream keys
- Add/Edit/Disable stream keys
- Auto-save to database

### ✅ Live Streaming
- Manual live start
- Scheduled live streaming
- Single video or playlist mode
- 24/7 loop support

### ✅ Stream Management
- Start/Stop individual streams
- Multiple concurrent streams
- Stream key rotation on error
- Real-time monitoring

### ✅ Dashboards
- Stream Keys Dashboard
- Live Monitoring Dashboard
- History & Statistics

### ✅ Advanced Features
- Re-Live from history
- YouTube API integration
- Automatic fallback
- Collision handling

---

## 🎯 Main Endpoints

### Dashboard
- `GET /dashboard/stream-keys` - Stream keys management
- `GET /dashboard/monitoring` - Live monitoring

### Live Streaming
- `POST /live/manual` - Start manual live
- `POST /live/stop/{session_id}` - Stop live
- `GET /live/active` - List active streams

### Scheduler
- `POST /schedule/create` - Schedule live
- `GET /schedule/list` - List schedules
- `POST /schedule/cancel/{id}` - Cancel schedule

### Re-Live
- `POST /relive/start` - Start re-live
- `POST /relive/schedule` - Schedule re-live
- `GET /relive/available-histories` - Get histories

### YouTube API
- `POST /youtube/create-live-setup` - Create broadcast + stream
- `POST /youtube/create-multiple-lives` - Create multiple setups

---

## 📖 Usage Examples

### 1. Add Stream Key

Via Dashboard:
```
http://localhost:8000/dashboard/stream-keys
→ Click "Add Stream Key"
→ Fill form
→ Submit
```

Via API:
```bash
curl -X POST "http://localhost:8000/stream-keys" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Lofi Main",
    "stream_key": "xxxx-xxxx-xxxx-xxxx"
  }'
```

### 2. Start Manual Live

```bash
curl -X POST "http://localhost:8000/live/manual" \
  -H "Content-Type: application/json" \
  -d '{
    "stream_key_id": 1,
    "playlist_id": 1,
    "mode": "playlist",
    "loop": true
  }'
```

### 3. Schedule Live

```bash
curl -X POST "http://localhost:8000/schedule/create" \
  -H "Content-Type: application/json" \
  -d '{
    "stream_key_id": 1,
    "scheduled_time": "2026-01-07T20:00:00",
    "playlist_id": 1,
    "mode": "playlist",
    "loop": true
  }'
```

### 4. Monitor Active Streams

```
http://localhost:8000/dashboard/monitoring
```

Real-time monitoring dengan:
- Runtime counter
- FFmpeg PID
- Stop button per stream
- Auto-refresh setiap 5 detik

---

## 🗂️ Project Structure

```
streamlive/
├── app/
│   ├── models/           # Database models
│   │   ├── stream_key.py
│   │   ├── live_session.py
│   │   ├── scheduled_live.py
│   │   └── live_history.py
│   ├── services/         # Business logic
│   │   ├── ffmpeg_service.py
│   │   ├── stream_control_service.py
│   │   ├── live_scheduler_service.py
│   │   ├── stream_key_rotation_service.py
│   │   └── youtube_api_service.py
│   ├── routers/          # API endpoints
│   │   ├── live.py
│   │   ├── schedule.py
│   │   ├── relive.py
│   │   ├── dashboard.py
│   │   ├── monitoring.py
│   │   └── youtube_api.py
│   ├── database.py       # Database config
│   ├── config.py         # App config
│   └── main.py           # FastAPI app
├── templates/            # Jinja2 templates
│   ├── stream_keys.html
│   ├── stream_key_form.html
│   └── monitoring.html
├── videos/               # Video storage
├── migrate_*.py          # Migration scripts
├── seed_*.py             # Seed scripts
├── requirements.txt      # Dependencies
└── .env                  # Environment variables
```

---

## 🔧 Configuration

### Environment Variables (.env)

```bash
# FFmpeg
FFMPEG_PATH=C:\ffmpeg\bin\ffmpeg.exe

# Database
DATABASE_URL=sqlite:///./data.db

# Stream Limits
MAX_CONCURRENT_STREAMS=10

# YouTube (optional)
YOUTUBE_STREAM_KEY=your-default-key
```

---

## 🎬 Workflow Examples

### Workflow 1: 24/7 Lofi Stream

```
1. Add stream key via dashboard
2. Upload videos or create playlist
3. Start manual live:
   - Stream Key: Lofi Main
   - Playlist: Chill Beats
   - Loop: ON
4. Monitor via dashboard
5. Stream runs 24/7
```

### Workflow 2: Scheduled Stream

```
1. Create schedule:
   - Time: 20:00 today
   - Stream Key: Evening Stream
   - Playlist: Study Music
2. Scheduler auto-starts at 20:00
3. Stream runs automatically
4. Monitor via dashboard
```

### Workflow 3: Multiple Concurrent Streams

```
1. Create 3 stream keys:
   - Lofi Main
   - Study Channel
   - Piano Stream

2. Start 3 concurrent lives:
   - Stream 1: Key A → Playlist 1
   - Stream 2: Key B → Playlist 2
   - Stream 3: Key C → Playlist 3

3. All running simultaneously!
4. Monitor all via dashboard
```

### Workflow 4: Re-Live from History

```
1. Go to /relive/available-histories
2. Select successful stream
3. Choose new stream key
4. Start re-live
5. Same content, different key
```

---

## 🛠️ Troubleshooting

### Server won't start

```bash
# Check Python version
python --version  # Should be 3.8+

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### FFmpeg not found

```bash
# Check FFmpeg installation
ffmpeg -version

# Update .env with correct path
FFMPEG_PATH=C:\path\to\ffmpeg.exe
```

### Database errors

```bash
# Re-run migrations
python migrate_stream_keys.py
python migrate_live_sessions.py
python migrate_scheduled_lives.py
```

### Stream won't start

1. Check stream key is active
2. Check video files exist
3. Check FFmpeg path is correct
4. Check logs for errors

---

## 📚 Documentation

Detailed guides available in project:
- Stream Keys Management
- Live Streaming API
- Scheduler System
- Re-Live Feature
- YouTube API Integration
- Stream Key Rotation
- Monitoring Dashboard

---

## 🔒 Security Notes

- Stream keys are masked in UI (****xyz1)
- Full keys only in edit forms
- Database stores full keys securely
- OAuth tokens in `.pickle` files (gitignored)

---

## 📝 Development

### Add New Router

```python
# app/routers/my_router.py
from fastapi import APIRouter

router = APIRouter(prefix="/my-route", tags=["My Feature"])

@router.get("/")
def my_endpoint():
    return {"message": "Hello"}

# app/main.py
from app.routers import my_router
app.include_router(my_router.router)
```

### Add New Service

```python
# app/services/my_service.py
class MyService:
    def do_something(self):
        pass

my_service = MyService()
```

---

## 🤝 Contributing

1. Fork repository
2. Create feature branch
3. Make changes
4. Test thoroughly
5. Submit pull request

---

## 📄 License

MIT License

---

## 🎉 Credits

Built with:
- FastAPI
- SQLAlchemy
- APScheduler
- FFmpeg
- Bootstrap 5
- YouTube Data API v3

---

## 📞 Support

For issues or questions:
1. Check documentation
2. Review logs
3. Check GitHub issues
4. Contact support

---

**Happy Streaming! 🎥✨**
