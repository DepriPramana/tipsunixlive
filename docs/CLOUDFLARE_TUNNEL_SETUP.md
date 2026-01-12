# Cloudflare Tunnel Setup Guide for StreamLive

This guide shows how to expose StreamLive to the internet using **Cloudflare Tunnel** (free, with custom domain and SSL).

## Why Cloudflare Tunnel?

| Feature | Cloudflare Tunnel | Ngrok Free |
|---------|-------------------|------------|
| **Price** | ✅ **Free** | ✅ Free (limited) |
| **Custom Domain** | ✅ **Yes** | ❌ Paid only |
| **Persistent URL** | ✅ **Yes** | ❌ Changes on restart |
| **SSL/HTTPS** | ✅ **Auto** | ✅ Yes |
| **WebSocket** | ✅ **Yes** | ✅ Yes |
| **Rate Limit** | ✅ **Unlimited** | ❌ 40 req/min |
| **DDoS Protection** | ✅ **Yes** | ❌ No |

---

## Prerequisites

- A domain registered with Cloudflare (or transferred to Cloudflare DNS)
- Linux server with StreamLive installed
- Root/sudo access

---

## Architecture

```
Internet 
  ↓
Cloudflare CDN (DDoS Protection, SSL, Caching)
  ↓
Cloudflare Tunnel (Encrypted)
  ↓
Nginx (localhost:80) → Static files, reverse proxy
  ↓
Uvicorn (localhost:8000) → FastAPI app
```

---

## Step 1: Install Cloudflared

```bash
# Download cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Or via package manager
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update && sudo apt install cloudflared
```

Verify installation:
```bash
cloudflared --version
```

---

## Step 2: Authenticate with Cloudflare

```bash
cloudflared tunnel login
```

This will open a browser window. Select your domain and authorize.

---

## Step 3: Create Tunnel

```bash
cloudflared tunnel create streamlive
```

**Output:**
```
Tunnel credentials written to /home/username/.cloudflared/UUID.json
Created tunnel streamlive with id UUID
```

**Important:** Save the `UUID` shown in the output!

---

## Step 4: Configure Tunnel

Create config file:
```bash
mkdir -p ~/.cloudflared
nano ~/.cloudflared/config.yml
```

Add the following (replace placeholders):

```yaml
tunnel: streamlive
credentials-file: /home/YOUR_USERNAME/.cloudflared/YOUR_TUNNEL_UUID.json

ingress:
  # Route for StreamLive
  - hostname: streamlive.yourdomain.com
    service: http://localhost:80
    originRequest:
      noTLSVerify: true
  
  # Catch-all rule (required)
  - service: http_status:404
```

**Replace:**
- `YOUR_USERNAME` with your Linux username
- `YOUR_TUNNEL_UUID.json` with the actual credentials file name
- `yourdomain.com` with your domain

---

## Step 5: Setup DNS

Run this command to automatically create DNS record:

```bash
cloudflared tunnel route dns streamlive streamlive.yourdomain.com
```

**Or manually** in Cloudflare Dashboard:
1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Select your domain
3. **DNS** → **Add Record**:
   - Type: `CNAME`
   - Name: `streamlive`
   - Target: `YOUR_TUNNEL_UUID.cfargotunnel.com`
   - Proxy status: **Proxied** (orange cloud ☁️)

---

## Step 6: Install & Configure Nginx

Install Nginx:
```bash
sudo apt update
sudo apt install nginx -y
```

Create StreamLive config:
```bash
sudo nano /etc/nginx/sites-available/streamlive
```

Add this configuration:

```nginx
server {
    listen 80;
    server_name localhost;

    client_max_body_size 500M;  # For large video uploads

    # Static files
    location /static/ {
        alias /path/to/streamlive/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /thumbnails/ {
        alias /path/to/streamlive/thumbnails/;
        expires 7d;
        add_header Cache-Control "public";
    }

    # Proxy to Uvicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        
        # WebSocket support (for /ws/monitoring and /ws/logs)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts for video uploads
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
```

**Replace** `/path/to/streamlive/` with your actual StreamLive installation path.

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/streamlive /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Step 7: Test Tunnel

Start tunnel manually to test:
```bash
cloudflared tunnel run streamlive
```

Open browser and visit: `https://streamlive.yourdomain.com`

You should see StreamLive login page!

Press `Ctrl+C` to stop the test.

---

## Step 8: Install as System Service

Install cloudflared as a service:
```bash
sudo cloudflared service install
```

Start and enable:
```bash
sudo systemctl start cloudflared
sudo systemctl enable cloudflared
sudo systemctl status cloudflared
```

---

## Step 9: Update Google OAuth

Since you now have a new domain, update Google OAuth settings:

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Edit your **OAuth 2.0 Client ID**
3. Add **Authorized redirect URIs**:
   ```
   https://streamlive.yourdomain.com/oauth2callback
   ```
4. Click **Save**

5. Download the updated `client_secrets.json`

6. In StreamLive:
   - Go to **Settings** page
   - Upload the new `client_secrets.json`

---

## Monitoring & Troubleshooting

### Check Tunnel Status
```bash
sudo systemctl status cloudflared
```

### View Logs
```bash
sudo journalctl -u cloudflared -f
```

### Restart Tunnel
```bash
sudo systemctl restart cloudflared
```

### List All Tunnels
```bash
cloudflared tunnel list
```

### Delete Tunnel (if needed)
```bash
cloudflared tunnel delete streamlive
```

---

## Security Best Practices

### 1. Enable Cloudflare WAF (Web Application Firewall)

In Cloudflare Dashboard:
- **Security** → **WAF** → Enable **Managed Rules**

### 2. Enable Rate Limiting

- **Security** → **Rate Limiting** → Create rule:
  - Match: `streamlive.yourdomain.com/*`
  - Requests: 100 per minute
  - Action: Block

### 3. Enable Bot Protection

- **Security** → **Bots** → Enable **Bot Fight Mode**

### 4. Restrict Access by Country (Optional)

- **Security** → **WAF** → **Custom Rules**
- Create rule to block/allow specific countries

---

## Performance Optimization

### 1. Enable Cloudflare Caching

In Cloudflare Dashboard:
- **Caching** → **Configuration**
- **Caching Level**: Standard
- **Browser Cache TTL**: 4 hours

### 2. Enable Auto Minify

- **Speed** → **Optimization**
- Enable: JavaScript, CSS, HTML

### 3. Enable Brotli Compression

- **Speed** → **Optimization**
- Enable **Brotli**

---

## Common Issues

### Issue: "tunnel credentials file not found"

**Solution:**
```bash
# Check if credentials file exists
ls -la ~/.cloudflared/

# If missing, recreate tunnel
cloudflared tunnel delete streamlive
cloudflared tunnel create streamlive
```

### Issue: "502 Bad Gateway"

**Solution:**
1. Check if Uvicorn is running:
   ```bash
   ps aux | grep uvicorn
   ```

2. Check if Nginx is running:
   ```bash
   sudo systemctl status nginx
   ```

3. Check Nginx logs:
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```

### Issue: WebSocket not working

**Solution:**
Ensure Nginx config has WebSocket headers (already included in config above).

---

## Updating StreamLive

When you update StreamLive code, you only need to restart Uvicorn:

```bash
# If running manually
# Stop with Ctrl+C, then restart

# If running as systemd service
sudo systemctl restart streamlive
```

**No need to restart** Cloudflare Tunnel or Nginx.

---

## Cost

**Total Cost: $0/month** 🎉

- Cloudflare Tunnel: Free
- Cloudflare DNS: Free
- Cloudflare SSL: Free
- Cloudflare CDN: Free
- Cloudflare DDoS Protection: Free

---

## Alternative: Direct Cloudflare Tunnel (Without Nginx)

If you don't want to use Nginx, you can point Cloudflare Tunnel directly to Uvicorn:

**Config:**
```yaml
ingress:
  - hostname: streamlive.yourdomain.com
    service: http://localhost:8000  # Direct to Uvicorn
  - service: http_status:404
```

**Pros:**
- Simpler setup
- One less service to manage

**Cons:**
- No static file caching
- No custom headers/rewrites
- Less control over request handling

**Recommendation:** Use Nginx for production deployments.

---

## Next Steps

After setup is complete:

1. ✅ Test all StreamLive features
2. ✅ Create YouTube broadcasts
3. ✅ Test WebSocket features (Monitoring Dashboard, Logs)
4. ✅ Upload videos and verify thumbnails load
5. ✅ Enable Cloudflare security features

---

## Support

For issues:
- Cloudflare Tunnel: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/
- StreamLive: Check application logs in `logs/` directory
