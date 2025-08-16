import cloudinary
import cloudinary.uploader
import cloudinary.api
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)


class CloudinaryService:
    """Service for handling Cloudinary operations."""
    
    @staticmethod
    def upload_payment_screenshot(file, student_id, timestamp=None):
        """Upload payment screenshot to Cloudinary."""
        try:
            # Create a unique public_id
            import time
            timestamp = timestamp or int(time.time())
            public_id = f"payments/{student_id}_{timestamp}"
            
            # Upload to Cloudinary
            result = cloudinary.uploader.upload(
                file,
                public_id=public_id,
                folder="mess_payments",
                resource_type="image",
                format="jpg",
                quality="auto:good",
                width=1200,
                height=1600,
                crop="limit",
                tags=["payment", "screenshot", str(student_id)]
            )
            
            logger.info(f"Payment screenshot uploaded successfully: {result['secure_url']}")
            return {
                'success': True,
                'url': result['secure_url'],
                'public_id': result['public_id'],
                'bytes': result.get('bytes', 0),
                'format': result.get('format', 'jpg')
            }
            
        except Exception as e:
            logger.error(f"Failed to upload payment screenshot: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def upload_qr_code(qr_image, student_id, version=1):
        """Upload QR code image to Cloudinary."""
        try:
            public_id = f"qr_codes/{student_id}_v{version}"
            
            result = cloudinary.uploader.upload(
                qr_image,
                public_id=public_id,
                folder="mess_qr_codes",
                resource_type="image",
                format="png",
                quality="auto:best",
                tags=["qr_code", str(student_id), f"version_{version}"]
            )
            
            logger.info(f"QR code uploaded successfully: {result['secure_url']}")
            return {
                'success': True,
                'url': result['secure_url'],
                'public_id': result['public_id']
            }
            
        except Exception as e:
            logger.error(f"Failed to upload QR code: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def delete_file(public_id):
        """Delete file from Cloudinary."""
        try:
            result = cloudinary.uploader.destroy(public_id)
            logger.info(f"File deleted from Cloudinary: {public_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to delete file from Cloudinary: {str(e)}")
            return {'result': 'error', 'error': str(e)}
    
    @staticmethod
    def get_file_info(public_id):
        """Get file information from Cloudinary."""
        try:
            result = cloudinary.api.resource(public_id)
            return {
                'success': True,
                'data': result
            }
        except Exception as e:
            logger.error(f"Failed to get file info: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def cleanup_old_files(folder, days_old=30):
        """Clean up old files from Cloudinary."""
        try:
            from datetime import datetime, timedelta
            
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            # Get all resources in folder
            resources = cloudinary.api.resources(
                type="upload",
                prefix=folder,
                max_results=500
            )
            
            deleted_count = 0
            for resource in resources.get('resources', []):
                created_at = datetime.fromisoformat(resource['created_at'].replace('Z', '+00:00'))
                
                if created_at < cutoff_date:
                    CloudinaryService.delete_file(resource['public_id'])
                    deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} old files from {folder}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old files: {str(e)}")
            return 0