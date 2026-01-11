from cryptography.fernet import Fernet
import base64
import hashlib
from app.config import SECRET_KEY

def _get_fernet_key(secret: str) -> bytes:
    """Derive a 32-byte base64 encoded key from the secret string."""
    # SHA-256 hash gives 32 bytes
    key_bytes = hashlib.sha256(secret.encode()).digest()
    # Base64 encode it for Fernet
    return base64.urlsafe_b64encode(key_bytes)

# Initialize Fernet with the derived key
cipher_suite = Fernet(_get_fernet_key(SECRET_KEY))

def encrypt_value(value: str) -> str:
    """Encrypt a string value."""
    if not value:
        return ""
    try:
        encrypted_bytes = cipher_suite.encrypt(value.encode())
        return encrypted_bytes.decode()
    except Exception as e:
        print(f"Encryption error: {e}")
        return value

def decrypt_value(encrypted_value: str) -> str:
    """Decrypt an encrypted string value."""
    if not encrypted_value:
        return ""
    try:
        decrypted_bytes = cipher_suite.decrypt(encrypted_value.encode())
        return decrypted_bytes.decode()
    except Exception:
        # Fallback: maybe it wasn't encrypted yet? return as is
        return encrypted_value
