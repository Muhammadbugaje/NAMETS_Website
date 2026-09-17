from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def user_holds_office(user, office_names):
    if user.is_superuser:
        return True
    return user.office_assignments.filter(
        office__name__in=office_names,
        is_active=True
    ).exists()


def office_required(*office_names):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if not user_holds_office(request.user, office_names):
                raise PermissionDenied("You don't have access to this page.")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator