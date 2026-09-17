from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.hashers import make_password
from django.utils.crypto import get_random_string

from accounts.models import User, Office, OfficeAssignment
from accounts.decorators import office_required
from accounts.forms import UserCreationForm
from core.email_utils import send_templated_email
from core.models import EmailLog

import csv
import io
import random
import string


# ============================================================
# USER MANAGEMENT
# ============================================================

@office_required('ICT Head')
def user_list(request):
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    gender_filter = request.GET.get('gender', '')
    office_filter = request.GET.get('office', '')
    alumni_filter = request.GET.get('alumni', '')
    view_mode = request.GET.get('view', 'cards')

    users = User.objects.all().order_by('-date_joined')

    if query:
        users = users.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(username__icontains=query) |
            Q(matric_number__icontains=query)
        )

    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)

    if gender_filter:
        users = users.filter(gender=gender_filter)

    if alumni_filter == 'yes':
        users = users.filter(is_alumni=True)
    elif alumni_filter == 'no':
        users = users.filter(is_alumni=False)

    if office_filter:
        users = users.filter(
            office_assignments__office_id=office_filter,
            office_assignments__is_active=True,
        ).distinct()

    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    alumni_count = User.objects.filter(is_alumni=True).count()
    exco_count = User.objects.filter(office_assignments__is_active=True).distinct().count()

    paginator = Paginator(users, 20)
    page = request.GET.get('page')
    users_page = paginator.get_page(page)

    offices = Office.objects.all()

    context = {
        'users': users_page,
        'query': query,
        'status_filter': status_filter,
        'gender_filter': gender_filter,
        'office_filter': office_filter,
        'alumni_filter': alumni_filter,
        'view_mode': view_mode,
        'offices': offices,
        'total_users': total_users,
        'active_users': active_users,
        'alumni_count': alumni_count,
        'exco_count': exco_count,
    }
    return render(request, 'ict/user_list.html', context)


@office_required('ICT Head')
def user_detail(request, user_id):
    user = get_object_or_404(User, id=user_id)
    assignments = user.office_assignments.filter(is_active=True)
    all_offices = Office.objects.all()
    return render(request, 'ict/user_detail.html', {
        'target_user': user,
        'assignments': assignments,
        'all_offices': all_offices,
    })


@office_required('ICT Head')
def add_user(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)

        if form.is_valid():
            user = form.save()
            temporary_password = user._temporary_password

            office_id = request.POST.get('office')
            if office_id:
                office = get_object_or_404(Office, id=office_id)
                display_label = request.POST.get('display_label', '')
                OfficeAssignment.objects.create(
                    user=user,
                    office=office,
                    display_label=display_label,
                )

            send_templated_email(
                subject="Your NAMETS Account Credentials",
                recipients=[user.email],
                template_name='emails/exco_credentials.html',
                context={
                    'user': user,
                    'username': user.email,
                    'temp_password': temporary_password,
                }
            )

            messages.success(
                request,
                f"✅ User {user.get_full_name()} created! "
                f"Login credentials sent to {user.email}."
            )
            return redirect('ict:user_detail', user_id=user.id)

        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

    else:
        form = UserCreationForm()

    offices = Office.objects.all()
    return render(request, 'ict/add_user.html', {
        'form': form,
        'offices': offices,
    })


@office_required('ICT Head')
def edit_user(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.middle_name = request.POST.get('middle_name', user.middle_name)
        user.phone_number = request.POST.get('phone_number', user.phone_number)
        user.matric_number = request.POST.get('matric_number', user.matric_number)
        user.gender = request.POST.get('gender', user.gender)
        user.is_alumni = 'is_alumni' in request.POST
        user.save()
        messages.success(request, f"✅ User {user.get_full_name()} updated successfully!")
        return redirect('ict:user_detail', user_id=user.id)

    return render(request, 'ict/edit_user.html', {'target_user': user})


@office_required('ICT Head')
def toggle_user_status(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user == request.user:
        messages.error(request, "You cannot suspend your own account.")
        return redirect('ict:user_detail', user_id=user.id)

    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])
    status = "activated" if user.is_active else "suspended"
    messages.success(request, f"User {user.get_full_name()} has been {status}.")
    return redirect('ict:user_detail', user_id=user.id)


@office_required('ICT Head')
def assign_office(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        office_id = request.POST.get('office')
        display_label = request.POST.get('display_label', '')

        if office_id:
            office = get_object_or_404(Office, id=office_id)
            if OfficeAssignment.objects.filter(user=user, office=office, is_active=True).exists():
                messages.warning(request, f"{user.get_full_name()} already holds that office.")
            else:
                OfficeAssignment.objects.create(
                    user=user,
                    office=office,
                    display_label=display_label,
                )
                messages.success(request, f"Office '{office.name}' assigned to {user.get_full_name()}.")
        return redirect('ict:user_detail', user_id=user.id)

    offices = Office.objects.all()
    return render(request, 'ict/assign_office.html', {
        'target_user': user,
        'offices': offices,
    })


@office_required('ICT Head')
def remove_office(request, assignment_id):
    assignment = get_object_or_404(OfficeAssignment, id=assignment_id, is_active=True)
    user = assignment.user
    assignment.is_active = False
    assignment.save(update_fields=['is_active'])
    messages.success(request, f"Removed '{assignment.office.name}' from {user.get_full_name()}.")
    return redirect('ict:user_detail', user_id=user.id)


@office_required('ICT Head')
def resend_credentials(request, user_id):
    user = get_object_or_404(User, id=user_id)

    chars = string.ascii_letters + string.digits + '!@#$%^&*'
    new_password = ''.join(random.choice(chars) for _ in range(12))
    user.set_password(new_password)
    user.must_change_password = True
    user.save()

    send_templated_email(
        subject="Your NAMETS Account Credentials (Re-sent)",
        recipients=[user.email],
        template_name='emails/exco_credentials.html',
        context={
            'user': user,
            'temp_password': new_password,
        }
    )
    messages.success(request, f"✅ Credentials re-sent to {user.email}.")
    return redirect('ict:user_detail', user_id=user.id)


@office_required('ICT Head')
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect('ict:user_detail', user_id=user.id)

    if request.method == 'POST':
        user.delete()
        messages.success(request, f"User {user.get_full_name()} has been permanently deleted.")
        return redirect('ict:user_list')

    return redirect('ict:user_detail', user_id=user.id)


# ============================================================
# EMAIL LOGS
# ============================================================

@office_required('ICT Head')
def email_logs(request):
    status_filter = request.GET.get('status', '')
    provider_filter = request.GET.get('provider', '')
    category_filter = request.GET.get('category', '')
    query = request.GET.get('q', '')

    logs = EmailLog.objects.all().order_by('-sent_at')

    if status_filter:
        logs = logs.filter(status=status_filter)
    if provider_filter:
        logs = logs.filter(provider=provider_filter)
    if category_filter:
        logs = logs.filter(category=category_filter)
    if query:
        logs = logs.filter(
            Q(recipient_email__icontains=query) |
            Q(subject__icontains=query)
        )

    paginator = Paginator(logs, 50)
    page = request.GET.get('page')
    logs_page = paginator.get_page(page)

    total_sent = EmailLog.objects.filter(status='sent').count()
    total_failed = EmailLog.objects.filter(status='failed').count()
    today_count = EmailLog.objects.filter(sent_at__date=timezone.now().date()).count()

    return render(request, 'ict/email_logs.html', {
        'logs': logs_page,
        'total_sent': total_sent,
        'total_failed': total_failed,
        'today_count': today_count,
        'status_filter': status_filter,
        'provider_filter': provider_filter,
        'category_filter': category_filter,
        'query': query,
    })


@office_required('ICT Head')
def resend_failed_email(request, log_id):
    log = get_object_or_404(EmailLog, id=log_id, status='failed')
    log.status = 'sent'
    log.save()
    messages.success(request, "Email marked as re-sent.")
    return redirect('ict:email_logs')


# ============================================================
# SMART EXCO IMPORT / RECONCILIATION
# ============================================================
# Matching priority: phone → email
#
# If a GraduationProfile matches:
#   - reuse the existing User
#   - update their details from the CSV row
#   - mark them as active EXCO (is_alumni=False, is_active=True)
#   - create/reactivate their OfficeAssignment
#   - DELETE the GraduationProfile (they are no longer alumni)
#   - log an audit entry
#
# If no match:
#   - create a brand-new User
#   - generate a temporary password
#   - create OfficeAssignment
#   - send credentials email
# ============================================================


def _normalise(value):
    """Normalize incoming CSV values for reliable matching."""
    if value is None:
        return ''
    return str(value).strip()


def _normalise_email(value):
    return _normalise(value).lower()


def _normalise_phone(value):
    """
    Normalize phone numbers enough to handle values such as:
        +2348012345678
        08012345678
        2348012345678
    """
    value = _normalise(value)
    if not value:
        return ''

    if value.startswith('+'):
        digits = '+' + ''.join(ch for ch in value[1:] if ch.isdigit())
    else:
        digits = ''.join(ch for ch in value if ch.isdigit())

    # Nigeria-specific normalization
    if digits.startswith('+234'):
        return '0' + digits[4:]

    if digits.startswith('234') and len(digits) >= 13:
        return '0' + digits[3:]

    return digits


def _user_field_exists(field_name):
    return field_name in {
        f.name for f in User._meta.get_fields() if hasattr(f, 'name')
    }


def _find_graduation_profile(phone='', email=''):
    """
    Find a GraduationProfile using phone first, then email.

    Returns (profile_or_None, error_or_None).

    If phone and email resolve to two different profiles, an
    ambiguity error is returned.
    """
    from governance.models import GraduationProfile

    phone_match = None
    email_match = None

    # -------- PHONE MATCH --------
    if phone:
        # Match against GraduationProfile.phone_number AND the linked User.phone_number
        profiles_qs = GraduationProfile.objects.select_related('user')

        for profile in profiles_qs:
            # Try the profile's own snapshot first
            profile_phone = _normalise_phone(getattr(profile, 'phone_number', '') or '')

            # Fall back to the linked user's phone
            if not profile_phone and profile.user:
                profile_phone = _normalise_phone(profile.user.phone_number or '')

            if profile_phone and profile_phone == phone:
                if phone_match is not None and phone_match.pk != profile.pk:
                    return None, "Multiple GraduationProfiles matched this phone number."
                phone_match = profile

    # -------- EMAIL MATCH --------
    if email:
        profiles_qs = GraduationProfile.objects.select_related('user')

        for profile in profiles_qs:
            profile_email = _normalise_email(getattr(profile, 'email', '') or '')

            if not profile_email and profile.user:
                profile_email = _normalise_email(profile.user.email or '')

            if profile_email and profile_email == email:
                if email_match is not None and email_match.pk != profile.pk:
                    return None, "Multiple GraduationProfiles matched this email address."
                email_match = profile

    # -------- BOTH MATCH DIFFERENT PEOPLE --------
    if phone_match and email_match and phone_match.pk != email_match.pk:
        return (
            None,
            "Phone matched one GraduationProfile while email matched another. "
            "Row was not imported."
        )

    # -------- RETURN THE WINNER --------
    return phone_match or email_match, None


def _update_user_from_import(user, row):
    """
    Update only fields that actually exist on User.
    Never touches password — existing credentials remain.
    """
    changed_fields = []

    field_map = {
        'first_name':   ['first_name', 'firstname', 'first'],
        'last_name':    ['last_name', 'lastname', 'surname', 'last'],
        'middle_name':  ['middle_name', 'middlename', 'middle'],
        'email':        ['email', 'email_address'],
        'phone_number': ['phone_number', 'phone', 'mobile', 'mobile_number'],
        'matric_number':['matric_number', 'matric', 'matric_no'],
        'gender':       ['gender', 'sex'],
    }

    for user_field, possible_columns in field_map.items():
        if not _user_field_exists(user_field):
            continue

        value = ''
        for column in possible_columns:
            if column in row:
                value = _normalise(row.get(column))
                break

        if not value:
            continue

        if user_field == 'email':
            value = _normalise_email(value)
            if getattr(user, 'email') != value:
                user.email = value
                user.username = value
                changed_fields.extend(['email', 'username'])
            continue

        if user_field == 'phone_number':
            value = _normalise_phone(value)

        if getattr(user, user_field) != value:
            setattr(user, user_field, value)
            changed_fields.append(user_field)

    # Reconciliation = active EXCO again
    if user.is_alumni:
        user.is_alumni = False
        changed_fields.append('is_alumni')

    if not user.is_active:
        user.is_active = True
        changed_fields.append('is_active')

    # Email is the login identifier
    if user.email and user.username != user.email:
        user.username = user.email
        if 'username' not in changed_fields:
            changed_fields.append('username')

    if changed_fields:
        user.save(update_fields=list(dict.fromkeys(changed_fields)))

    return user


def _create_new_import_user(row):
    """Create a fresh User when no GraduationProfile matches."""
    email = _normalise_email(row.get('email') or row.get('email_address') or '')
    first_name = _normalise(row.get('first_name') or row.get('firstname') or row.get('first') or '')
    last_name = _normalise(row.get('last_name') or row.get('lastname') or row.get('surname') or row.get('last') or '')

    if not email:
        raise ValueError("Email is required for a new user.")
    if not first_name:
        raise ValueError("First name is required for a new user.")
    if not last_name:
        raise ValueError("Last name is required for a new user.")

    if User.objects.filter(email__iexact=email).exists():
        raise ValueError(
            f"A User with email {email} already exists, "
            "but no matching GraduationProfile was found."
        )

    temporary_password = get_random_string(
        length=12,
        allowed_chars=(
            "abcdefghijkmnopqrstuvwxyz"
            "ABCDEFGHJKLMNPQRSTUVWXYZ"
            "23456789!@#$%"
        )
    )

    user = User(
        email=email,
        username=email,
        first_name=first_name,
        last_name=last_name,
        middle_name=_normalise(row.get('middle_name') or row.get('middlename') or ''),
        phone_number=_normalise_phone(
            row.get('phone_number') or row.get('phone') or row.get('mobile') or ''
        ),
        matric_number=_normalise(
            row.get('matric_number') or row.get('matric') or row.get('matric_no') or ''
        ),
        gender=_normalise(row.get('gender') or row.get('sex') or ''),
        is_alumni=False,
        is_active=True,
        must_change_password=True,
    )
    user.set_password(temporary_password)
    user.save()

    user._temporary_password = temporary_password
    return user


def _assign_imported_office(user, row):
    """
    Create or reactivate the OfficeAssignment for this user.
    Respects unique_together on (user, office).
    """
    office_name = _normalise(
        row.get('office') or row.get('office_name') or row.get('position') or ''
    )
    display_label = _normalise(
        row.get('display_label') or row.get('title') or row.get('role') or ''
    )

    if not office_name:
        return None

    office = Office.objects.filter(name__iexact=office_name).first()
    if not office:
        raise ValueError(f"Office '{office_name}' does not exist.")

    assignment, created = OfficeAssignment.objects.get_or_create(
        user=user,
        office=office,
        defaults={
            'display_label': display_label,
            'is_active': True,
        }
    )

    if not created:
        assignment.display_label = display_label
        assignment.is_active = True
        assignment.save(update_fields=['display_label', 'is_active'])

    return assignment


@office_required('ICT Head')
def import_exco(request):
    """
    Smart EXCO CSV importer.

    Matching order:
        phone -> email

    Matching a GraduationProfile:
        - reuse its existing User
        - update User details
        - mark user as current EXCO
        - DELETE the GraduationProfile (they are no longer alumni)
        - create/reactivate OfficeAssignment
        - write an AuditLog entry

    No match:
        - create a brand-new User
        - generate a temporary password
        - create OfficeAssignment
        - send credentials email

    Reports: total processed, reconciled, created, failed, with per-row errors.
    """
    if request.method != 'POST':
        return render(request, 'ict/import_exco.html')

    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        messages.error(request, "Please select a CSV file.")
        return redirect('ict:import_exco')

    if not uploaded_file.name.lower().endswith('.csv'):
        messages.error(request, "Please upload a CSV file.")
        return redirect('ict:import_exco')

    try:
        decoded = uploaded_file.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        messages.error(request, "The CSV file must be UTF-8 encoded.")
        return redirect('ict:import_exco')

    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        messages.error(request, "The CSV file has no header row.")
        return redirect('ict:import_exco')

    # Normalize column names
    normalized_rows = []
    for raw_row in reader:
        row = {}
        for key, value in raw_row.items():
            if key is None:
                continue
            normalized_key = (
                key.strip()
                .lower()
                .replace(' ', '_')
                .replace('-', '_')
            )
            row[normalized_key] = _normalise(value)
        normalized_rows.append(row)

    imported = 0
    reconciled = 0
    created = 0
    failed = 0
    errors = []
    new_users_to_email = []  # (user, temp_password) — email sent AFTER all rows
    reconciled_users = []    # (user, old_office_name, new_office_name) — for audit

    for row_number, row in enumerate(normalized_rows, start=2):
        try:
            phone = _normalise_phone(
                row.get('phone')
                or row.get('phone_number')
                or row.get('mobile')
                or row.get('mobile_number')
                or ''
            )
            email = _normalise_email(
                row.get('email') or row.get('email_address') or ''
            )

            if not phone and not email:
                raise ValueError("At least a phone number or email is required.")

            with transaction.atomic():

                graduation_profile, profile_error = _find_graduation_profile(
                    phone=phone,
                    email=email,
                )

                if profile_error:
                    raise ValueError(profile_error)

                # ==================================================
                # RECONCILIATION PATH — existing alumni returns
                # ==================================================
                if graduation_profile:
                    user = getattr(graduation_profile, 'user', None)

                    if user is None:
                        raise ValueError(
                            "GraduationProfile matched, but no linked User was found."
                        )

                    # Grab old office info for the audit note BEFORE we change anything
                    old_offices = list(
                        user.office_assignments.filter(is_active=True)
                        .values_list('office__name', flat=True)
                    )
                    old_office_name = old_offices[0] if old_offices else '—'

                    _update_user_from_import(user, row)
                    assignment = _assign_imported_office(user, row)

                    new_office_name = (
                        assignment.office.name if assignment else '—'
                    )

                    # Consume the graduation profile — they're back on the EXCO
                    graduation_profile.delete()

                    reconciled += 1
                    reconciled_users.append(
                        (user, old_office_name, new_office_name)
                    )

                # ==================================================
                # BRAND-NEW USER PATH
                # ==================================================
                else:
                    user = _create_new_import_user(row)
                    _assign_imported_office(user, row)
                    created += 1
                    new_users_to_email.append(
                        (user, getattr(user, '_temporary_password', None))
                    )

                imported += 1

        except Exception as exc:
            failed += 1
            errors.append(f"Row {row_number}: {exc}")

    # ============================================================
    # POST-IMPORT: send emails to new users
    # ============================================================
    email_failures = []
    for user, temp_password in new_users_to_email:
        if not temp_password:
            continue
        try:
            send_templated_email(
                subject="Your NAMETS Account Credentials",
                recipients=[user.email],
                template_name='emails/exco_credentials.html',
                context={
                    'user': user,
                    'username': user.email,
                    'temp_password': temp_password,
                }
            )
        except Exception as e:
            email_failures.append(f"{user.email}: {e}")

    # ============================================================
    # POST-IMPORT: audit log for reconciled users
    # ============================================================
    try:
        from governance.models import AuditLog
        for user, old_office, new_office in reconciled_users:
            AuditLog.objects.create(
                user=request.user,
                action='update',
                target_model='User',
                target_id=user.pk,
                object_repr=(
                    f"Re-onboarded {user.get_full_name() or user.email}: "
                    f"{old_office} → {new_office}"
                ),
                changes={
                    'reconciled_from_graduation_profile': True,
                    'old_office': old_office,
                    'new_office': new_office,
                },
            )
    except Exception:
        # Audit logging should never break the import
        pass

    # ============================================================
    # REPORT BACK
    # ============================================================
    if reconciled:
        messages.success(
            request,
            f"✅ Reconciled {reconciled} returning alumni into current EXCO "
            f"(GraduationProfile{'s' if reconciled != 1 else ''} deleted)."
        )

    if created:
        messages.success(
            request,
            f"✅ Created {created} new EXCO user{'s' if created != 1 else ''}. "
            f"Credentials emails dispatched."
        )

    if email_failures:
        for msg in email_failures[:5]:
            messages.warning(request, f"⚠️ Credentials email failed for {msg}")
        if len(email_failures) > 5:
            messages.warning(
                request,
                f"...and {len(email_failures) - 5} more email failure(s)."
            )

    if failed:
        for error in errors[:10]:
            messages.error(request, f"❌ {error}")
        if len(errors) > 10:
            messages.error(
                request,
                f"...and {len(errors) - 10} more row error(s)."
            )

    messages.info(
        request,
        f"Import finished: {imported} processed, "
        f"{reconciled} reconciled, "
        f"{created} created, "
        f"{failed} failed."
    )

    return redirect('ict:import_exco')