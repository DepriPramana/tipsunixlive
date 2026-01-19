"""
Script utility untuk mengoptimalkan video background agar sesuai dengan standar YouTube Streaming.
Script ini akan melakukan re-encode dengan GOP (Group of Pictures) size 2 detik (60 frames),
sehingga aman digunakan dengan mode '-c:v copy' pada aplikasi utama.

Cara penggunaan:
    python optimize_video.py "path/to/video.mp4"

Output:
    File baru dengan suffix _optimized.mp4 akan dibuat di folder yang sama.
"""
import sys
import os
import subprocess
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Konfigurasi Path FFmpeg
# Sesuaikan ini jika FFmpeg tidak ada di System PATH
FFMPEG_PATH = "ffmpeg"

def optimize_video(input_path: str):
    """
    Re-encode video dengan setting GOP yang ketat untuk YouTube.
    """
    if not os.path.exists(input_path):
        logger.error(f"File tidak ditemukan: {input_path}")
        return

    # Generate output path
    directory = os.path.dirname(input_path)
    filename = os.path.basename(input_path)
    name, ext = os.path.splitext(filename)
    output_path = os.path.join(directory, f"{name}_optimized{ext}")
    
    logger.info(f"Input: {input_path}")
    logger.info(f"Output: {output_path}")

    # Build FFmpeg command sesuai request user
    # ffmpeg -i input.mp4 -c:v libx264 -preset medium -b:v 4000k -g 60 -keyint_min 60 -sc_threshold 0 -r 30 -s 1920x1080 -c:a aac -b:a 128k output.mp4
    cmd = [
        FFMPEG_PATH,
        '-i', input_path,
        
        # Video settings
        '-c:v', 'libx264',
        '-preset', 'medium',        # Quality preset
        '-b:v', '4000k',            # Video bitrate
        '-maxrate', '4500k',        # Max bitrate cap
        '-bufsize', '8000k',        # Buffer size
        '-g', '60',                 # GOP size (Keyframe interval) -> 2 seconds at 30fps
        '-keyint_min', '60',        # Min keyframe interval
        '-sc_threshold', '0',       # Disable scene change detection for strict GOP
        '-r', '30',                 # Frame rate
        '-s', '1920x1080',          # Resolution
        '-pix_fmt', 'yuv420p',      # Pixel format for compatibility
        
        # Audio settings
        '-c:a', 'aac',
        '-b:a', '128k',             # Audio bitrate
        '-ar', '44100',             # Sample rate
        
        # Output flags
        '-y',                       # Overwrite output
        output_path
    ]

    logger.info("Menjalankan FFmpeg...")
    logger.info(f"Command: {' '.join(cmd)}")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Baca output real-time (opsional, untuk melihat progress)
        for line in process.stderr:
            print(line, end='')

        process.wait()

        if process.returncode == 0:
            logger.info("✅ Optimasi berhasil!")
            logger.info(f"Silakan gunakan file '{output_path}' sebagai background di aplikasi.")
        else:
            logger.error("❌ Optimasi gagal.")
            
    except Exception as e:
        logger.error(f"Terjadi kesalahan: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python optimize_video.py <path_to_video>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    optimize_video(input_file)
