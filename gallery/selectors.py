from .models import GalleryImage

def get_recent_gallery_images(limit=6):
    """Return the most recent gallery images, ordered by newest gallery first."""
    return GalleryImage.objects.select_related('gallery').order_by('-gallery__created_at', 'order')[:limit]