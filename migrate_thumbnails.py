from sqlalchemy import create_engine, text
from app.config import DATABASE_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            # Check if column exists
            result = conn.execute(text("PRAGMA table_info(videos)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'thumbnail_path' not in columns:
                logger.info("Adding thumbnail_path column to videos table...")
                conn.execute(text("ALTER TABLE videos ADD COLUMN thumbnail_path VARCHAR"))
                conn.commit()
                logger.info("Migration successful!")
            else:
                logger.info("Column thumbnail_path already exists.")
                
        except Exception as e:
            logger.error(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
