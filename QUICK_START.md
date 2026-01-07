# StreamLive - Quick Access Guide

Server running di: **http://localhost:8000**

## 📱 Dashboards

### 1. Stream Keys Management
```
http://localhost:8000/dashboard/stream-keys
```
**Features:**
- ➕ Add stream key
- ✏️ Edit stream key  
- ⏸️ Enable/Disable
- 🗑️ Delete
- 📊 View status (Active/Idle/Live)

---

### 2. Live Monitoring
```
http://localhost:8000/dashboard/monitoring
```
**Features:**
- 🔴 Real-time live streams
- ⏱️ Runtime counter (auto-update)
- 🔑 Stream key info
- 📹 Video/Playlist info
- 🛑 Stop button per stream
- 🔄 Auto-refresh (5 detik)

---

### 3. Admin Dashboard (Original)
```
http://localhost:8000/admin/
```
**Features:**
- 📁 Videos management
- 📋 Playlists
- 🎬 Live control
- 📅 Schedule
- 📊 History

---

## 🎯 API Endpoints

### Live Streaming

**Start Manual Live:**
```bash
POST http://localhost:8000/live/manual
{
  "stream_key_id": 1,
  "playlist_id": 1,
  "mode": "playlist",
  "loop": true
}
```

**Stop Live:**
```bash
POST http://localhost:8000/live/stop/{session_id}
```

**List Active:**
```bash
GET http://localhost:8000/live/active
```

---

### Scheduler

**Create Schedule:**
```bash
POST http://localhost:8000/schedule/create
{
  "stream_key_id": 1,
  "scheduled_time": "2026-01-07T20:00:00",
  "playlist_id": 1,
  "mode": "playlist"
}
```

**List Schedules:**
```bash
GET http://localhost:8000/schedule/list
```

**Cancel Schedule:**
```bash
POST http://localhost:8000/schedule/cancel/{schedule_id}
```

---

### Re-Live

**Get Histories:**
```bash
GET http://localhost:8000/relive/available-histories
```

**Start Re-Live:**
```bash
POST http://localhost:8000/relive/start
{
  "history_id": 1,
  "stream_key_id": 2,
  "loop": true
}
```

**Schedule Re-Live:**
```bash
POST http://localhost:8000/relive/schedule
{
  "history_id": 1,
  "stream_key_id": 2,
  "scheduled_time": "2026-01-07T20:00:00"
}
```

---

### YouTube API

**Create Live Setup:**
```bash
POST http://localhost:8000/youtube/create-live-setup
{
  "broadcast_title": "Lofi Beats 24/7",
  "stream_name": "Lofi Main",
  "description": "Chill beats"
}
```

**Create Multiple Lives:**
```bash
POST http://localhost:8000/youtube/create-multiple-lives
{
  "setups": [
    {"broadcast_title": "Lofi 1", "stream_name": "Main"},
    {"broadcast_title": "Lofi 2", "stream_name": "Backup"}
  ]
}
```

---

## 🚀 Quick Workflows

### Workflow 1: Start 24/7 Stream

1. **Add Stream Key**
   ```
   http://localhost:8000/dashboard/stream-keys
   → Add Stream Key
   → Name: "Lofi Main"
   → Key: "xxxx-xxxx-xxxx-xxxx"
   ```

2. **Start Live**
   ```bash
   curl -X POST http://localhost:8000/live/manual \
     -H "Content-Type: application/json" \
     -d '{"stream_key_id": 1, "playlist_id": 1, "mode": "playlist", "loop": true}'
   ```

3. **Monitor**
   ```
   http://localhost:8000/dashboard/monitoring
   ```

---

### Workflow 2: Schedule Stream

1. **Create Schedule**
   ```bash
   curl -X POST http://localhost:8000/schedule/create \
     -d '{"stream_key_id": 1, "scheduled_time": "2026-01-07T20:00:00", "playlist_id": 1, "mode": "playlist"}'
   ```

2. **Check Schedules**
   ```
   http://localhost:8000/admin/schedule
   ```

3. **Auto-starts at scheduled time**

---

### Workflow 3: Multiple Concurrent Streams

1. **Add 3 Stream Keys**
   - Lofi Main
   - Study Channel
   - Piano Stream

2. **Start 3 Lives**
   ```bash
   # Stream 1
   curl -X POST http://localhost:8000/live/manual \
     -d '{"stream_key_id": 1, "playlist_id": 1, "mode": "playlist"}'
   
   # Stream 2
   curl -X POST http://localhost:8000/live/manual \
     -d '{"stream_key_id": 2, "playlist_id": 2, "mode": "playlist"}'
   
   # Stream 3
   curl -X POST http://localhost:8000/live/manual \
     -d '{"stream_key_id": 3, "playlist_id": 3, "mode": "playlist"}'
   ```

3. **Monitor All**
   ```
   http://localhost:8000/dashboard/monitoring
   ```

---

## 📖 API Documentation

**Swagger UI:**
```
http://localhost:8000/docs
```

**ReDoc:**
```
http://localhost:8000/redoc
```

---

## 🔧 Troubleshooting

### Dashboard 404 Error
✅ **Fixed!** Routers sudah ditambahkan ke `main.py`

Server akan auto-reload. Refresh browser.

### Stream Won't Start
1. Check stream key is active
2. Check video/playlist exists
3. Check FFmpeg path in `.env`
4. Check logs

### FFmpeg Error
1. Verify FFmpeg installed: `ffmpeg -version`
2. Update `.env`: `FFMPEG_PATH=C:\path\to\ffmpeg.exe`
3. Restart server

---

## 📝 Notes

- **Auto-refresh:** Monitoring dashboard updates every 5 seconds
- **Runtime:** Updates every 1 second (client-side)
- **Max Concurrent:** Default 10 streams (configurable in `.env`)
- **Stream Keys:** Masked in UI for security

---

**Happy Streaming! 🎥✨**
