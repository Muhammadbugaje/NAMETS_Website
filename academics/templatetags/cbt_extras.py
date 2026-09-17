"""
Template filters for the CBT module.
"""

from django import template

register = template.Library()


@register.filter
def format_seconds(value):
    """
    Turn an integer number of seconds into MM:SS or H:MM:SS.
    Used by the test timer and result-page time display.
    """
    try:
        total = int(value)
    except (TypeError, ValueError):
        return '—'
    if total < 0:
        total = 0
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


@register.filter
def percentage_of(value, total):
    """Safe percentage: percentage_of(3, 12) → '25.0'"""
    try:
        v = float(value)
        t = float(total)
        if t == 0:
            return '0.0'
        return f"{(v / t * 100):.1f}"
    except (TypeError, ValueError):
        return '0.0'


@register.filter
def score_band_color(band):
    """Map score band to a hex color for inline use."""
    return {
        'excellent':  '#38a169',
        'good':       '#3182ce',
        'fair':       '#d69e2e',
        'needs_work': '#c0392b',
    }.get(band, '#C8A951')


@register.filter
def difficulty_label(value):
    """'easy' → 'Easy', 'medium' → 'Medium', 'hard' → 'Hard'"""
    return {'easy': 'Easy', 'medium': 'Medium', 'hard': 'Hard'}.get(value, value.title())


@register.filter
def difficulty_color(value):
    """Difficulty → pill background color."""
    return {
        'easy':   '#e8f2ec',
        'medium': '#f5e9c8',
        'hard':   '#fdecea',
    }.get(value, '#f0f4f2')


@register.filter
def difficulty_text_color(value):
    """Difficulty → pill text color."""
    return {
        'easy':   '#1a6b3c',
        'medium': '#8a6a1a',
        'hard':   '#9b2c2c',
    }.get(value, '#0F3D2E')
    
    
    
from django import template

register = template.Library()


@register.filter
def get_option_text(question, option_letter):
    """
    Return the text of a specific option on a CBT question.
    Usage in template: {{ q|get_option_text:q.correct_option }}
    """
    if not question or not option_letter:
        return ''
    letter = str(option_letter).lower().strip()

    # Try direct attribute access (question.option_a, option_b, ...)
    attr_name = f'option_{letter}'
    if hasattr(question, attr_name):
        value = getattr(question, attr_name, '')
        return value or ''

    # Fallback: question.options dict
    if hasattr(question, 'options'):
        opts = question.options
        if isinstance(opts, dict):
            return opts.get(letter, '')

    return ''    
    