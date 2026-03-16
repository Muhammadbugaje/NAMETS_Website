# utils/admin_helpers.py
from django.utils.html import format_html
import cloudinary.utils

def cloudinary_thumbnail(image_field, width=50, height=50):
    """
    Return an HTML img tag for a Cloudinary image thumbnail.
    image_field should be a CloudinaryField instance (e.g., obj.image).
    """
    if image_field and image_field.public_id:
        url, _ = cloudinary.utils.cloudinary_url(
            image_field.public_id,
            width=width,
            height=height,
            crop="fill"  # crops to exactly fit dimensions
        )
        return format_html(
            '<img src="{}" style="max-width:{}px; max-height:{}px; border-radius:4px;" />',
            url, width, height
        )
    return "No Image"