from core.importers.spec import ImportSpec, ColumnSpec
from core.importers.registry import register
from .models import (
    Result, Evaluation, CompetitionResult, TimetableEntry,
    Course, Tutor, IslamiyyaCourse, IslamiyyaRegistration,
    IslamiyyaSettings,
)


# ============================================================
# 1. EVALUATION RESULTS
# ============================================================

class ResultImportSpec(ImportSpec):
    key = "results"
    label = "Evaluation Results"
    model = Result
    columns = [
        ColumnSpec("student_name", "Student Name", example="Aminu Abdullah"),
        ColumnSpec("registration_number", "Registration Number", required=False, example="U22EE1001"),
        ColumnSpec("marks_obtained", "Marks Obtained", example="78"),
        ColumnSpec("grade", "Grade", required=False, example="A"),
        ColumnSpec("remarks", "Remarks", required=False, example="Excellent work"),
    ]

    def validate_row(self, row, form_params=None):
        errors = super().validate_row(row, form_params)
        if form_params and 'evaluation' not in form_params:
            errors.append("No evaluation selected for this import.")
        if row.get('marks_obtained'):
            try:
                float(row['marks_obtained'])
            except ValueError:
                errors.append(f"'Marks Obtained' must be a number, got '{row['marks_obtained']}'.")
        return errors

    def build_instance(self, row, form_params=None):
        evaluation = form_params.get('evaluation')
        if not evaluation:
            raise ValueError("No evaluation provided for result import.")
        return Result.objects.create(
            evaluation=evaluation,
            student_name=row['student_name'],
            registration_number=row.get('registration_number', ''),
            marks_obtained=float(row['marks_obtained']),
            grade=row.get('grade', ''),
            remarks=row.get('remarks', ''),
        )


# ============================================================
# 2. COMPETITION RESULTS
# ============================================================

class CompetitionResultImportSpec(ImportSpec):
    key = "competition-results"
    label = "Competition Results"
    model = CompetitionResult
    columns = [
        ColumnSpec("event_name", "Event Name", example="NAMETS Week 2026"),
        ColumnSpec("category", "Category", required=False, example="Musabaqah 60 Hizb"),
        ColumnSpec("position", "Position", required=False, example="1st"),
        ColumnSpec("participant_name", "Participant Name", example="Maryam Bello"),
        ColumnSpec("department", "Department", required=False, example="Electrical Engineering"),
        ColumnSpec("points", "Points", required=False, example="95"),
        ColumnSpec("year", "Year", required=False, example="2025/2026"),
        ColumnSpec("order", "Order", required=False, example="1"),
    ]

    def validate_row(self, row, form_params=None):
        errors = super().validate_row(row, form_params)
        for numeric_field in ('points', 'order'):
            if row.get(numeric_field):
                try:
                    float(row[numeric_field])
                except ValueError:
                    errors.append(f"'{numeric_field.title()}' must be a number, got '{row[numeric_field]}'.")
        return errors

    def build_instance(self, row):
        return CompetitionResult.objects.create(
            event_name=row['event_name'],
            category=row.get('category', ''),
            position=row.get('position', 'participant'),
            participant_name=row['participant_name'],
            department=row.get('department', ''),
            points=float(row['points']) if row.get('points') else None,
            year=row.get('year', ''),
            order=int(row['order']) if row.get('order') else 0,
        )

    def row_from_instance(self, instance):
        return {
            'event_name': instance.event_name,
            'category': instance.category,
            'position': instance.position,
            'participant_name': instance.participant_name,
            'department': instance.department,
            'points': instance.points,
            'year': instance.year,
            'order': instance.order,
        }


# ============================================================
# 3. TIMETABLE
# ============================================================

class TimetableImportSpec(ImportSpec):
    key = "timetable"
    label = "Timetable Entries"
    model = TimetableEntry
    DAY_NAMES = {name.lower(): num for num, name in TimetableEntry.DAYS_OF_WEEK}

    columns = [
        ColumnSpec("day", "Day", example="1", choices=[str(n) for n in range(1, 8)]),
        ColumnSpec("time_range", "Time Range", example="8-10 or 09:00-11:00"),
        ColumnSpec("course_name", "Course Name", example="EEE201 Tutorial"),
        ColumnSpec("venue", "Venue", required=False, example="ECE Lecture Hall 2"),
        ColumnSpec("entry_type", "Type", example="tutorial", choices=["tutorial", "islamiyya"]),
        ColumnSpec("level", "Level", required=False, example="level1", choices=["level1", "level2"]),
    ]

    def validate_row(self, row, form_params=None):
        errors = super().validate_row(row, form_params)

        day_raw = row.get("day", "").strip()
        if day_raw:
            try:
                day_int = int(day_raw)
                if day_int not in range(1, 8):
                    errors.append(f"'Day' must be 1–7, got {day_raw}")
            except ValueError:
                errors.append(f"'Day' must be a number, got '{day_raw}'")

        time_range = row.get("time_range", "").strip()
        if time_range:
            parts = time_range.replace(" ", "").split("-")
            if len(parts) != 2:
                errors.append(f"'Time Range' must be like '8-10' or '09:00-11:00', got '{time_range}'")

        entry_type = row.get("entry_type", "").lower()
        if entry_type and entry_type not in ("tutorial", "islamiyya"):
            errors.append("'Type' must be 'tutorial' or 'islamiyya'")

        level = row.get("level", "").lower()
        if level and level not in ("level1", "level2"):
            errors.append("'Level' must be 'level1' or 'level2'")

        return errors

    def build_instance(self, row):
        from datetime import datetime
        day = int(row["day"].strip())
        time_range = row["time_range"].strip()
        parts = time_range.replace(" ", "").split("-")
        start_str, end_str = parts
        if ":" not in start_str:
            start_str += ":00"
        if ":" not in end_str:
            end_str += ":00"
        start = datetime.strptime(start_str, "%H:%M").time()
        end = datetime.strptime(end_str, "%H:%M").time()

        return TimetableEntry.objects.create(
            day=day,
            time_start=start,
            time_end=end,
            course_name=row["course_name"].strip()[:200],
            venue=row.get("venue", "").strip()[:200],
            entry_type=row["entry_type"].strip().lower(),
            level=row.get("level", "level1").strip().lower(),
            is_active=True,
        )

    def row_from_instance(self, instance):
        time_range = f"{instance.time_start.strftime('%H:%M')}-{instance.time_end.strftime('%H:%M')}"
        return {
            "day": instance.day,
            "time_range": time_range,
            "course_name": instance.course_name,
            "venue": instance.venue,
            "entry_type": instance.entry_type,
            "level": instance.level,
        }


# ============================================================
# 4. COURSES  (NEW)
# ============================================================

class CourseImportSpec(ImportSpec):
    key = "courses"
    label = "Courses"
    model = Course
    columns = [
        ColumnSpec("name", "Course Name", example="EEE201 Tutorial"),
        ColumnSpec("slug", "Slug", required=False, example="eee201-tutorial"),
        ColumnSpec("description", "Description", required=False, example="Weekly tutorial for EEE201"),
        ColumnSpec("course_type", "Type", example="tutorial", choices=["tutorial", "islamiyya"]),
        ColumnSpec("tutor_emails", "Tutor Emails", required=False,
                   example="tutor1@email.com, tutor2@email.com"),
        ColumnSpec("is_active", "Active", required=False, example="Yes", choices=["Yes", "No"]),
    ]

    def validate_row(self, row, form_params=None):
        errors = super().validate_row(row, form_params)
        ct = row.get("course_type", "").lower()
        if ct and ct not in ("tutorial", "islamiyya"):
            errors.append("'Type' must be 'tutorial' or 'islamiyya'")
        return errors

    def build_instance(self, row):
        from django.utils.text import slugify
        name = row["name"].strip()
        slug = (row.get("slug") or "").strip() or slugify(name)
        course, _ = Course.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "description": row.get("description", ""),
                "course_type": row.get("course_type", "tutorial").lower(),
                "is_active": (row.get("is_active", "Yes").lower() == "yes"),
            },
        )
        # Attach tutors by email
        emails = [e.strip() for e in (row.get("tutor_emails") or "").split(",") if e.strip()]
        for email in emails:
            t = Tutor.objects.filter(email__iexact=email).first()
            if t:
                course.tutors.add(t)
        return course

    def row_from_instance(self, instance):
        return {
            "name": instance.name,
            "slug": instance.slug,
            "description": instance.description,
            "course_type": instance.course_type,
            "tutor_emails": ", ".join(t.email for t in instance.tutors.all() if t.email),
            "is_active": "Yes" if instance.is_active else "No",
        }


# ============================================================
# 5. TUTORS  (NEW)
# ============================================================

class TutorImportSpec(ImportSpec):
    key = "tutors"
    label = "Tutors"
    model = Tutor
    columns = [
        ColumnSpec("name", "Full Name", example="Ustadh Ibrahim Musa"),
        ColumnSpec("email", "Email", required=False, example="ibrahim@email.com"),
        ColumnSpec("phone", "Phone", required=False, example="08012345678"),
        ColumnSpec("bio", "Bio", required=False, example="Senior tutor, Islamic Studies"),
        ColumnSpec("is_active", "Active", required=False, example="Yes", choices=["Yes", "No"]),
    ]

    def build_instance(self, row):
        return Tutor.objects.create(
            name=row["name"].strip(),
            email=row.get("email", "").strip(),
            phone=row.get("phone", "").strip(),
            bio=row.get("bio", "").strip(),
            is_active=(row.get("is_active", "Yes").lower() == "yes"),
        )

    def row_from_instance(self, instance):
        return {
            "name": instance.name,
            "email": instance.email,
            "phone": instance.phone,
            "bio": instance.bio,
            "is_active": "Yes" if instance.is_active else "No",
        }


# ============================================================
# 6. ISLAMIYYA COURSES  (NEW)
# ============================================================

class IslamiyyaCourseImportSpec(ImportSpec):
    key = "islamiyya-courses"
    label = "Islamiyya Courses"
    model = IslamiyyaCourse
    columns = [
        ColumnSpec("name", "Course Name", example="Tajweed"),
        ColumnSpec("is_active", "Active", required=False, example="Yes", choices=["Yes", "No"]),
    ]

    def build_instance(self, row):
        obj, _ = IslamiyyaCourse.objects.get_or_create(
            name=row["name"].strip(),
            defaults={"is_active": (row.get("is_active", "Yes").lower() == "yes")},
        )
        return obj

    def row_from_instance(self, instance):
        return {
            "name": instance.name,
            "is_active": "Yes" if instance.is_active else "No",
        }


# ============================================================
# 7. ISLAMIYYA REGISTRATIONS  (NEW)
# ============================================================

class IslamiyyaRegistrationImportSpec(ImportSpec):
    key = "islamiyya-registrations"
    label = "Islamiyya Registrations"
    model = IslamiyyaRegistration
    columns = [
        ColumnSpec("name", "Full Name", example="Fatima Ahmed"),
        ColumnSpec("email", "Email", example="fatima@email.com"),
        ColumnSpec("phone", "Phone", example="08012345678"),
        ColumnSpec("registration_number", "Registration Number", example="U22EE1001"),
        ColumnSpec("department", "Department", required=False, example="Electrical Engineering"),
        ColumnSpec("gender", "Gender", required=False, example="F", choices=["M", "F"]),
        ColumnSpec("level", "Level", example="beginner", choices=["beginner", "intermediate", "advanced"]),
        ColumnSpec("courses", "Courses", required=False, example="Tajweed, Fiqh"),
        ColumnSpec("other_course", "Other Course", required=False, example=""),
        ColumnSpec("payment_status", "Payment Status", required=False, example="pending",
                   choices=["pending", "paid", "waived"]),
        ColumnSpec("amount_paid", "Amount Paid", required=False, example="2000"),
        ColumnSpec("payment_method", "Payment Method", required=False, example="manual",
                   choices=["paystack", "manual", "cash", "waived"]),
    ]

    def validate_row(self, row, form_params=None):
        errors = super().validate_row(row, form_params)

        email = row.get("email", "").strip()
        if email and IslamiyyaRegistration.objects.filter(email__iexact=email).exists():
            errors.append(f"'{email}' already registered.")

        lvl = (row.get("level") or "").lower()
        if lvl and lvl not in ("beginner", "intermediate", "advanced"):
            errors.append("'Level' must be beginner / intermediate / advanced")

        ps = (row.get("payment_status") or "pending").lower()
        if ps not in ("pending", "paid", "waived"):
            errors.append("'Payment Status' must be pending / paid / waived")

        return errors

    def build_instance(self, row):
        # Find or create session (use current active one)
        session = IslamiyyaSettings.objects.filter(is_active=True).first()

        reg = IslamiyyaRegistration.objects.create(
            session_settings=session,
            name=row["name"].strip(),
            email=row["email"].strip(),
            phone=row.get("phone", "").strip(),
            registration_number=row.get("registration_number", "").strip(),
            department=row.get("department", "").strip(),
            gender=(row.get("gender") or "").strip() or None,
            level=(row.get("level") or "beginner").lower(),
            other_course=row.get("other_course", "").strip(),
        )

        # Attach courses by name (create if needed)
        for name in [c.strip() for c in (row.get("courses") or "").split(",") if c.strip()]:
            course, _ = IslamiyyaCourse.objects.get_or_create(name=name)
            reg.courses.add(course)

        # Payment
        ps = (row.get("payment_status") or "pending").lower()
        if ps == "paid":
            try:
                amount = float(row.get("amount_paid") or 0)
            except (ValueError, TypeError):
                amount = 0
            method = (row.get("payment_method") or "manual").lower()
            reg.mark_paid(amount=amount, method=method, reference="IMPORT")
            # Record to ledger
            from business.models import record_payment_to_ledger
            if session and session.account and amount > 0:
                record_payment_to_ledger(
                    amount=amount,
                    category='islamiyya_revenue',
                    description=f"[Import] Islamiyya {reg.application_id}: {reg.name}",
                    account=session.account,
                )
        elif ps == "waived":
            reg.mark_waived(by_user=None, note="Imported as waived")

        return reg

    def row_from_instance(self, instance):
        return {
            "name": instance.name,
            "email": instance.email,
            "phone": instance.phone,
            "registration_number": instance.registration_number,
            "department": instance.department or "",
            "gender": instance.gender or "",
            "level": instance.level,
            "courses": ", ".join(c.name for c in instance.courses.all()),
            "other_course": instance.other_course or "",
            "payment_status": instance.payment_status,
            "amount_paid": instance.amount_paid,
            "payment_method": instance.payment_method or "",
        }


# ============================================================
# REGISTER ALL
# ============================================================

register(ResultImportSpec())
register(CompetitionResultImportSpec())
register(TimetableImportSpec())
register(CourseImportSpec())
register(TutorImportSpec())
register(IslamiyyaCourseImportSpec())
register(IslamiyyaRegistrationImportSpec())