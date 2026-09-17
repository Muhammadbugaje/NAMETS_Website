from django.db import transaction
from django.template.loader import render_to_string
from core.importers.spec import ImportSpec, ColumnSpec
from core.importers.registry import register
from core.email_utils import send_mail
from .models import User, Office, Department, OfficeAssignment
from .utils import generate_default_password


class ExcoImportSpec(ImportSpec):
    key = "exco"
    label = "EXCO Members"
    model = User

    columns = [
        ColumnSpec("full_name", "Full Name", example="Ahmadu Bello"),
        ColumnSpec("email", "Email", example="mib@gmail.com"),
        ColumnSpec("phone_number", "Phone Number", required=False, example="08012345678"),
        ColumnSpec("matric_number", "Matric Number", required=False, example="U22EE1031"),
        ColumnSpec("department", "Department", required=False, example="Electrical Engineering"),
        ColumnSpec("office", "Office", example="ICT I"),
        ColumnSpec("gender_label", "Gender Label", required=False, example="Brother"),
    ]

    # ============================================================
    # HELPERS — GraduationProfile lookups (safe against missing app)
    # ============================================================

    def _has_graduation_profile(self, user):
        """True if this user has a GraduationProfile (i.e. is a graduating EXCO)."""
        try:
            from governance.models import GraduationProfile
            return GraduationProfile.objects.filter(user=user).exists()
        except (ImportError, Exception):
            return False

    def _delete_graduation_profile(self, user):
        """Delete the user's graduation profile if present. Returns count deleted."""
        try:
            from governance.models import GraduationProfile
            deleted, _ = GraduationProfile.objects.filter(user=user).delete()
            return deleted
        except (ImportError, Exception):
            return 0

    def _find_existing_user(self, row):
        """
        Look up an existing user by PHONE first, then EMAIL.
        Returns (user, matched_by) or (None, None).
        """
        phone = (row.get('phone_number') or '').strip()
        email = (row.get('email') or '').strip()

        # Phone wins — more unique in Nigeria, emails change
        if phone:
            user = User.objects.filter(phone_number=phone).first()
            if user:
                return user, 'phone'

        # Fall back to email
        if email:
            user = User.objects.filter(email__iexact=email).first()
            if user:
                return user, 'email'

        return None, None

    # ============================================================
    # VALIDATION
    # ============================================================

    def validate_row(self, row, form_params=None):
        errors = super().validate_row(row, form_params)

        existing, matched_by = self._find_existing_user(row)

        if existing:
            # A match is OK only if they're a graduating EXCO we can reconcile
            is_graduate = (
                self._has_graduation_profile(existing) or existing.is_alumni
            )
            if not is_graduate:
                errors.append(
                    f"A user with this {matched_by} already exists "
                    f"({existing.get_full_name() or existing.username} · {existing.email}) "
                    f"and is NOT a graduate. Re-onboarding only applies to alumni. "
                    f"If this is a genuine duplicate, remove the row or edit the record manually."
                )

        # Office must exist
        office_name = (row.get('office') or '').strip()
        if office_name and not Office.objects.filter(name__iexact=office_name).exists():
            errors.append(
                f"'{office_name}' doesn't match any existing Office. "
                f"Check spelling, or create this office in Django admin first."
            )

        return errors

    # ============================================================
    # BUILD — dispatch to reconcile or normal create
    # ============================================================

    @transaction.atomic
    def build_instance(self, row, form_params=None):
        existing, matched_by = self._find_existing_user(row)

        if existing:
            is_graduate = (
                self._has_graduation_profile(existing) or existing.is_alumni
            )
            if is_graduate:
                return self._reconcile_user(existing, row, matched_by)

            # Shouldn't reach here if validate_row ran, but be safe
            raise ValueError(
                f"User {existing.email} already exists and is not a graduate — "
                f"cannot re-onboard."
            )

        return self._create_new_user(row)

    # ============================================================
    # PATH A — RECONCILE (alumni → new EXCO)
    # ============================================================

    def _reconcile_user(self, user, row, matched_by):
        """
        This user was an alumni (has GraduationProfile) and is being re-onboarded.
        - Delete graduation profile
        - Update their details with the uploaded row
        - Reactivate account, force password change
        - Create new OfficeAssignment
        """
        # ---- Parse name ----
        names = row['full_name'].strip().split(' ', 2)
        first_name = names[0] if len(names) >= 1 else ''
        middle_name = names[1] if len(names) >= 3 else ''
        last_name = names[-1] if len(names) >= 2 else ''

        # ---- Department ----
        department = user.department
        if row.get('department'):
            dept_name = row['department'].strip()
            department, _ = Department.objects.get_or_create(
                name__iexact=dept_name,
                defaults={'name': dept_name, 'code': dept_name[:10].upper()},
            )

        # ---- Delete graduation profile ----
        deleted_count = self._delete_graduation_profile(user)

        # ---- Update user ----
        user.first_name = first_name
        user.middle_name = middle_name
        user.last_name = last_name
        if row.get('phone_number'):
            user.phone_number = row['phone_number'].strip()
        if row.get('matric_number'):
            user.matric_number = row['matric_number'].strip()
        user.department = department
        user.is_alumni = False
        user.is_active = True
        user.must_change_password = True

        # New temp password
        temp_password = generate_default_password()
        user.set_password(temp_password)
        user.save()

        # ---- Office assignment ----
        office = Office.objects.get(name__iexact=row['office'])
        gender_label = (row.get('gender_label') or '').strip()
        display_label = f"{office.name} ({gender_label})" if gender_label else ''

        # Deactivate any other active assignments (they shouldn't exist post-handover,
        # but just in case a stale one is still flagged active)
        OfficeAssignment.objects.filter(
            user=user, is_active=True
        ).exclude(office=office).update(is_active=False)

        # Create or reactivate the target office assignment
        OfficeAssignment.objects.update_or_create(
            user=user,
            office=office,
            defaults={
                'display_label': display_label,
                'is_active': True,
            },
        )

        # ---- Public "Meet the EXCO" stub ----
        self._maybe_create_executive_stub(user, office, gender_label)

        # ---- Send fresh credentials ----
        self._send_credentials_email(user, temp_password, reconciled=True)

        return user

    # ============================================================
    # PATH B — CREATE (fresh onboarding)
    # ============================================================

    def _create_new_user(self, row):
        names = row['full_name'].strip().split(' ', 2)
        first_name = names[0] if len(names) >= 1 else ''
        middle_name = names[1] if len(names) >= 3 else ''
        last_name = names[-1] if len(names) >= 2 else ''

        department = None
        if row.get('department'):
            dept_name = row['department'].strip()
            department, _ = Department.objects.get_or_create(
                name__iexact=dept_name,
                defaults={'name': dept_name, 'code': dept_name[:10].upper()},
            )

        temp_password = generate_default_password()

        user = User.objects.create_user(
            username=row['email'],
            email=row['email'],
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            phone_number=row.get('phone_number', ''),
            matric_number=row.get('matric_number', ''),
            department=department,
            must_change_password=True,
            password=temp_password,
        )

        office = Office.objects.get(name__iexact=row['office'])
        gender_label = (row.get('gender_label') or '').strip()
        display_label = f"{office.name} ({gender_label})" if gender_label else ''

        OfficeAssignment.objects.create(
            user=user,
            office=office,
            display_label=display_label,
        )

        self._maybe_create_executive_stub(user, office, gender_label)
        self._send_credentials_email(user, temp_password, reconciled=False)

        return user

    # ============================================================
    # SHARED HELPERS
    # ============================================================

    def _maybe_create_executive_stub(self, user, office, gender_label):
        """
        Creates/updates a stub entry on the public "Meet the EXCO" page.
        Uses update_or_create so promoted alumni get their new role reflected.
        """
        try:
            from community.models import Executive, ExecutiveYear
            active_year = ExecutiveYear.objects.filter(is_active=True).first()
            if not active_year:
                return

            role_label = f"{office.name} ({gender_label})" if gender_label else office.name
            full_name = f"{user.first_name} {user.last_name}".strip()

            Executive.objects.update_or_create(
                name=full_name,
                year=active_year,
                defaults={'role': role_label},
            )
        except (ImportError, Exception):
            pass

    def _send_credentials_email(self, user, temp_password, reconciled=False):
        """Send the credentials email with temporary password."""
        html = render_to_string('emails/exco_credentials.html', {
            'user': user,
            'temp_password': temp_password,
            'reconciled': reconciled,
        })

        sent = send_mail(
            subject="Your NAMETS Website Account",
            recipients=[user.email],
            html_message=html,
        )

        if not sent:
            raise RuntimeError(
                f"Account for {user.email} was created, but the credentials "
                f"email failed to send. Use 'Reset password' in Django admin "
                f"for this user before they can log in."
            )


# Register the import spec
register(ExcoImportSpec())