from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from django.core.files.base import ContentFile

import re
from django.utils import timezone

def generate_initials_avatar(user):
    """Fallback avatar: circular image with user's initials."""
    initials = f"{user.first_name[:1]}{user.last_name[:1]}".upper() or "?"
    size = 300
    img = Image.new('RGB', (size, size), color='#1B3A2E')
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 120)
    except IOError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), initials, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((size - text_w) / 2, (size - text_h) / 2 - bbox[1]),
        initials, fill='#C8A951', font=font
    )

    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return ContentFile(buffer.getvalue(), name=f'{user.username}_avatar.png')



def generate_default_password():
    """
    Generate a temporary password: Namets<year>!
    The year is read from the active ExecutiveYear (e.g., "2025/2026" → "2025").
    Falls back to the current calendar year if no ExecutiveYear is active.
    """
    try:
        from community.models import ExecutiveYear
        active_year = ExecutiveYear.objects.filter(is_active=True).first()
        if active_year:
            match = re.match(r'(\d{4})', active_year.year_label)
            year = match.group(1) if match else str(timezone.now().year)
        else:
            year = str(timezone.now().year)
    except ImportError:
        year = str(timezone.now().year)

    return f"Namets{year}!"
