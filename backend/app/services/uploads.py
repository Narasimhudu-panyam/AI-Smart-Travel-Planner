import cloudinary
import cloudinary.uploader
from fastapi import UploadFile

from app.config import Settings
from app.models import UploadResponse


async def upload_to_cloudinary(file: UploadFile, settings: Settings) -> UploadResponse:
    if not all([settings.cloudinary_cloud_name, settings.cloudinary_api_key, settings.cloudinary_api_secret]):
        return UploadResponse(
            url=f"demo://uploads/{file.filename}",
            public_id=file.filename or "demo-upload",
            resource_type="demo",
        )

    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )
    payload = await file.read()
    result = cloudinary.uploader.upload(payload, resource_type="auto", folder="smart-travel-planner")
    return UploadResponse(
        url=result["secure_url"],
        public_id=result["public_id"],
        resource_type=result["resource_type"],
    )
