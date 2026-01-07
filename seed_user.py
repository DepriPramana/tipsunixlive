import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app.models.user import User
from app.services.auth_service import get_password_hash
db = SessionLocal()
if not db.query(User).filter(User.username == 'admin').first():
    admin_user = User(
        username='admin',
        hashed_password=get_password_hash('admin123'),
        is_admin=True
    )
    db.add(admin_user)
    db.commit()
    print('✅ User admin berhasil dibuat!')
else:
    print('⚠️ User admin sudah ada.')
db.close()