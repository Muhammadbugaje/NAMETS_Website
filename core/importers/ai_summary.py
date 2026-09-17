import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def summarize_import_errors(row_errors: list[dict]) -> str:
    """Optional Gemini-based plain-English error summary."""
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key or not row_errors:
        return ''

    raw = "\n".join(
        f"Row {e['row_number']}: {', '.join(e['errors'])}" for e in row_errors
    )
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(
            "Summarize these spreadsheet import errors in 2-3 plain sentences "
            "for a non-technical office holder, grouping similar issues together:\n\n" + raw
        )
        return response.text
    except Exception as e:
        logger.warning("AI error summary failed: %s", e)
        return ''