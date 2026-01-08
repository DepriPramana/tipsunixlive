# 🐧 Linux Deployment Guide - StreamLive

Dokumen ini menjelaskan spesifikasi minimum server dan panduan langkah-demi-langkah untuk menjalankan StreamLive di server Linux (Ubuntu/Debian).

## 🖥️ Minimum Server Requirements

Untuk menjalankan streaming 24/7 dengan stabil, berikut adalah rekomendasi spesifikasi:

| Komponen | Minimum (1 Stream) | Rekomendasi (3+ Streams) |
| :--- | :--- | :--- |
| **Sistem Operasi** | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| **CPU** | 1 Core (Shared) | 2-4 Cores (Dedicated) |
| **RAM** | 2 GB | 4 GB - 8 GB |
| **Penyimpanan** | 20 GB SSD | 50 GB+ SSD (Tergantung jumlah video) |
| **Bandwidth** | 10 Mbps Upload | 50 Mbps+ Upload (Dedicated) |

> [!IMPORTANT]
> FFmpeg memerlukan penggunaan CPU yang intensif. Jika Anda berencana melakukan transcoding (mengubah resolusi), CPU Load akan meningkat drastis.

---

## 🚀 Step-by-Step Setup

### 1. Instal Dependensi Sistem
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv ffmpeg git nginx
```

### 2. Konfigurasi Timezone
Sangat penting agar jadwal streaming dan log sesuai dengan waktu lokal Anda:
```bash
sudo timedatectl set-timezone Asia/Makassar
# Verifikasi
timedatectl
```

### 3. Persiapan Project
```bash
git clone <repository-url> streamlive
cd streamlive

# Buat Virtual Environment
python3 -m venv venv
source venv/bin/activate

# Instal Python Dependencies
pip install -r requirements.txt
pip install gunicorn uvicorn
```

### 4. Konfigurasi Environment & Database
```bash
cp .env.example .env
# Edit .env dan sesuaikan YOUTUBE_STREAM_KEY
nano .env

# Inisialisasi Database & Create Admin User
python3 init_db.py
python3 seed_user.py  # User: admin, Pass: admin123
```

### 5. Konfigurasi Autostart (Systemd)
Buat file service agar aplikasi berjalan otomatis di background:
```bash
sudo nano /etc/systemd/system/streamlive.service
```
Isi dengan:
```ini
[Unit]
Description=StreamLive FastAPI Application
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=/home/youruser/streamlive
Environment="PATH=/home/youruser/streamlive/venv/bin"
ExecStart=/home/youruser/streamlive/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 127.0.0.1:8000
Restart=always

[Install]
WantedBy=multi-user.target
```
*Ganti `/home/youruser/streamlive` dengan path folder Anda.*

Aktifkan service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable streamlive
sudo systemctl start streamlive
```

### 6. Reverse Proxy (Nginx) - Port 8787

Jika mengunakan Hestia CP taruh disini config dibawah
```bash
sudo nano /etc/nginx/conf.d/streamlive.conf
```
Jika linux biasa Gunakan Nginx untuk ekspos aplikasi ke internet via port 8787:
```bash
sudo nano /etc/nginx/sites-available/streamlive
```
Isi dengan:
```nginx
server {
    listen 8787;
    server_name your_server_ip;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket Support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```
Aktifkan konfigurasi:
```bash
sudo ln -s /etc/nginx/sites-available/streamlive /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 7. Firewall Setup
```bash
sudo ufw allow 8787/tcp
sudo ufw allow ssh
sudo ufw enable
```

---

## 🛠️ Troubleshooting
*   **Cek log aplikasi:** `journalctl -u streamlive -f`
*   **Cek log nginx:** `sudo tail -f /var/log/nginx/error.log`
*   **Restart Server:** `sudo systemctl restart streamlive`
*   **Cek log ffmpeg:** `sudo ss -antp | grep 1935`
*   **Kill ffmpeg:** `sudo pkill -9 ffmpeg`


