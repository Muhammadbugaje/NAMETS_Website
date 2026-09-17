# core/templatetags/dashboard_extras.py
from django import template

register = template.Library()

@register.filter
def first_value(dictionary):
    """Return the first value from a dictionary, or empty string if empty."""
    if not dictionary:
        return ''
    # Get first value from dict
    for value in dictionary.values():
        return value
    return ''