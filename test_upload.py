import requests
import os

# Create a dummy sound file
filename = "test_sound.mp3"
with open(filename, "wb") as f:
    f.write(b"dummy audio content")

url = "http://127.0.0.1:8000/upload/sound-effect"
files = {"file": (filename, open(filename, "rb"), "audio/mpeg")}

try:
    print(f"Uploading {filename} to {url}...")
    response = requests.post(url, files=files)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
finally:
    files["file"][1].close()
    if os.path.exists(filename):
        os.remove(filename)
