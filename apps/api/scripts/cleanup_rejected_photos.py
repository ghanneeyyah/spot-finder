import asyncio
import logging
import os
import sys
from pathlib import Path

import cloudinary.api
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine

# Ensure the app module is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.models import SpotPhoto
from app.database import normalize_database_url

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("cleanup")

async def run_cleanup() -> None:
    settings = get_settings()
    if not (settings.cloudinary_api_key and settings.cloudinary_api_secret and settings.cloudinary_cloud_name):
        log.error("Cloudinary credentials are not fully configured. Aborting.")
        return

    engine = create_async_engine(normalize_database_url(settings.database_url))
    
    try:
        async with engine.begin() as conn:
            # Target photos that have been explicitly rejected
            query = select(SpotPhoto.id, SpotPhoto.cloudinary_public_id).where(
                SpotPhoto.is_approved.is_(False),
                SpotPhoto.rejection_reason.is_not(None)
            )
            rows = (await conn.execute(query)).all()
            
            if not rows:
                log.info("No rejected photos found. Environment is clean.")
                return

            public_ids = [row.cloudinary_public_id for row in rows]
            row_ids = [row.id for row in rows]

            log.info("Purging %d rejected assets from Cloudinary...", len(public_ids))
            
            # Delete assets in bulk via the Cloudinary Admin API (runs in thread to avoid blocking)
            response = await asyncio.to_thread(
                cloudinary.api.delete_resources,
                public_ids,
                cloud_name=settings.cloudinary_cloud_name,
                api_key=settings.cloudinary_api_key.get_secret_value(),
                api_secret=settings.cloudinary_api_secret.get_secret_value(),
            )
            
            deleted_counts = response.get("deleted", {})
            log.info("Cloudinary API response: %s", deleted_counts)

            # Drop the orphaned records from the database
            await conn.execute(delete(SpotPhoto).where(SpotPhoto.id.in_(row_ids)))
            log.info("Removed %d records from the database.", len(row_ids))
            
    except Exception as exc:
        log.error("Asset cleanup failed: %s", exc, exc_info=True)
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_cleanup())