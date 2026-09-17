"""
CBT AI Report — rule-based generator.

Returns a personalized report string built from the test stats.
Bulletproof: never raises, never returns empty.

When you're ready to add Gemini, replace the body of
`generate_ai_report()` with a real API call — the view doesn't change.
"""

import logging

logger = logging.getLogger(__name__)


# ============================================================
#  PUBLIC ENTRY POINT
# ============================================================

def generate_report(*args, **kwargs):
    """
    Flexible entry point.
    Accepts a dict, an object with attributes, or keyword args.
    Always returns a non-empty string.
    """
    try:
        stats = _extract_stats(args, kwargs)
        logger.info(
            "[cbt_ai] generate_report stats: score=%s total=%s pct=%s",
            stats.get('score'), stats.get('total'), stats.get('percentage'),
        )
        text = _build_rule_based_report(stats)
        if not text or not text.strip():
            text = "Well done on completing the test! Keep practicing — consistency is key."
        logger.info("[cbt_ai] returning report (%d chars)", len(text))
        return text
    except Exception:
        logger.exception("[cbt_ai] generate_report crashed")
        return "Well done on completing the test! Keep practicing — consistency is key."


# ============================================================
#  STATS EXTRACTION — defensive
# ============================================================

_FIELDS = (
    'score', 'total', 'percentage', 'band',
    'per_difficulty', 'per_topic', 'wrong_ids',
    'time_taken_seconds', 'student_name', 'difficulty',
)


def _extract_stats(args, kwargs):
    data = {}

    # ---- positional dicts / objects ----
    for a in args:
        if isinstance(a, dict):
            for k in _FIELDS:
                if k in a:
                    data.setdefault(k, a[k])
        elif a is not None and hasattr(a, '__dict__') and not isinstance(a, (str, bytes)):
            for k in _FIELDS:
                if hasattr(a, k):
                    data.setdefault(k, getattr(a, k))

    # ---- kwargs ----
    for k, v in kwargs.items():
        if v is not None:
            data[k] = v

    # ---- nested wrappers (result=..., test=..., stats=...) ----
    for key in ('result', 'test', 'stats', 'report_data', 'data'):
        nested = data.get(key)
        if isinstance(nested, dict):
            for k in _FIELDS:
                if k in nested:
                    data.setdefault(k, nested[k])
        elif nested is not None and hasattr(nested, '__dict__'):
            for k in _FIELDS:
                if hasattr(nested, k):
                    data.setdefault(k, getattr(nested, k))

    # ---- normalize ----
    data['score'] = _to_int(data.get('score'))
    data['total'] = _to_int(data.get('total'))
    data['time_taken_seconds'] = _to_int(data.get('time_taken_seconds'))

    pct_raw = data.get('percentage')
    if pct_raw is None:
        data['percentage'] = (data['score'] / data['total'] * 100) if data['total'] else 0.0
    else:
        try:
            data['percentage'] = float(pct_raw)
        except (TypeError, ValueError):
            data['percentage'] = 0.0

    if not isinstance(data.get('per_difficulty'), dict):
        data['per_difficulty'] = {}
    if not isinstance(data.get('per_topic'), dict):
        data['per_topic'] = {}
    if not isinstance(data.get('wrong_ids'), (list, tuple)):
        data['wrong_ids'] = []

    data['student_name'] = (data.get('student_name') or '').strip()
    data['difficulty'] = (data.get('difficulty') or 'mixed').strip()

    return data


def _to_int(v):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


# ============================================================
#  REPORT BUILDER
# ============================================================

def _build_rule_based_report(s):
    score = s['score']
    total = s['total']
    pct = s['percentage']
    student = s['student_name']
    per_diff = s['per_difficulty']
    per_topic = s['per_topic']

    if total == 0:
        return (
            "We couldn't read your answers for this attempt. Please try the test "
            "again — the report will be ready next time."
        )

    parts = []
    parts.append(_opening(student, pct))
    parts.append(_score_line(score, total, pct))

    diff_best, diff_worst = _best_and_worst(per_diff)
    if diff_best and diff_worst:
        parts.append(
            f"You did especially well on {diff_best} questions, but {diff_worst} "
            f"questions were your weakest area. Focus your revision on "
            f"{diff_worst} topics first — that's where the biggest gains are waiting."
        )
    elif diff_best:
        parts.append(
            f"Your strongest category was {diff_best} — well done. "
            f"Keep that consistency across all difficulties."
        )

    topic_best, topic_worst = _best_and_worst(per_topic)
    if topic_best and topic_worst:
        parts.append(
            f"By topic: you showed real understanding of '{topic_best}', "
            f"while '{topic_worst}' needs more attention. Re-read that section "
            f"of your notes and try related past questions."
        )

    parts.append(_closing(pct))
    return "\n\n".join(parts)


def _opening(student, pct):
    pre = f"{student}, " if student else ""
    if pct >= 90: return f"{pre}MashaAllah — an excellent result. You've clearly mastered this material."
    if pct >= 75: return f"{pre}Great work — a strong, confident performance."
    if pct >= 60: return f"{pre}Good effort — you're on the right track with a solid foundation."
    if pct >= 40: return f"{pre}Not bad — with a bit more focused practice you'll improve quickly."
    return f"{pre}Don't be discouraged — every attempt is a step forward. Let's look at where to focus."


def _score_line(score, total, pct):
    if pct >= 90:
        return f"You scored {score}/{total} ({pct:.0f}%). This is an outstanding result — you're ready to help others too."
    if pct >= 75:
        return f"You scored {score}/{total} ({pct:.0f}%). A few slip-ups on the trickier questions, but your understanding is solid."
    if pct >= 60:
        return f"You scored {score}/{total} ({pct:.0f}%). You know the basics well — now it's about polishing the details."
    if pct >= 40:
        return f"You scored {score}/{total} ({pct:.0f}%). There's real progress here, but some gaps need filling."
    return f"You scored {score}/{total} ({pct:.0f}%). The foundation needs work — but that's the easiest thing to fix with consistent study."


def _closing(pct):
    if pct >= 90:
        return "Next step: help a friend or junior with this topic — teaching cements understanding better than anything else."
    if pct >= 75:
        return "Next step: review the specific questions you missed and try similar ones. You're close to a perfect score."
    if pct >= 60:
        return "Next step: focus on the topics where you lost the most marks, then retake this test in a few days to measure improvement."
    if pct >= 40:
        return "Next step: pick the two weakest topics and study them properly this week. Small, consistent sessions work better than long cramming."
    return "Next step: start with the basics — read through your notes on this course, then come back and try again. Every NAMETS scholar started somewhere."


def _best_and_worst(bucket):
    if not bucket:
        return None, None
    scored = []
    for label, d in bucket.items():
        if isinstance(d, dict):
            t = _to_int(d.get('total'))
            c = _to_int(d.get('correct'))
        else:
            t, c = 0, 0
        if t <= 0:
            continue
        scored.append((label, (c / t) * 100, c, t))
    if not scored:
        return None, None
    scored.sort(key=lambda x: (-x[1], -x[3]))
    if len(scored) == 1 or scored[0][1] == scored[-1][1]:
        return scored[0][0], None
    return scored[0][0], scored[-1][0]