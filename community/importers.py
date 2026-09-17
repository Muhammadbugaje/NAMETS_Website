
from core.importers.spec import ImportSpec, ColumnSpec
from core.importers.registry import register
from .models import Executive, ExecutiveYear

from .models import MembershipApplication, Skill


class ExecutiveImportSpec(ImportSpec):
    key = "executives"
    label = "Executives"
    model = Executive

    columns = [
        ColumnSpec("name", "Full Name", example="Aminu Abdullah Musa"),
        ColumnSpec("role", "Role", example="Wakeel"),
        ColumnSpec("year_label", "Year", example="2025/2026"),
        ColumnSpec("display_order", "Display Order", required=False, example="1"),
        ColumnSpec("contribution_summary", "Contribution Summary", required=False, example="Led the team..."),
    ]

    def validate_row(self, row):
        errors = super().validate_row(row)

        year_label = row.get("year_label", "").strip()
        if year_label and not ExecutiveYear.objects.filter(year_label__iexact=year_label).exists():
            errors.append(f"Year '{year_label}' not found. Create it first in admin (or use the + button).")

        return errors

    def build_instance(self, row):
        year_label = row.get("year_label", "").strip()
        year, _ = ExecutiveYear.objects.get_or_create(
            year_label=year_label,
            defaults={'display_order': 999}
        )

        return Executive.objects.create(
            name=row.get("name", "").strip(),
            role=row.get("role", "").strip(),
            year=year,
            display_order=int(row.get("display_order", 0)),
            contribution_summary=row.get("contribution_summary", "").strip(),
            is_active=True,
        )


register(ExecutiveImportSpec())



class MembershipImportSpec(ImportSpec):
    key = "membership_applications"
    label = "Membership Applications"
    model = MembershipApplication

    columns = [
        ColumnSpec("name", "Full Name", example="Aminu Abdullah Musa"),
        ColumnSpec("email", "Email", example="amin@email.com"),
        ColumnSpec("phone", "Phone", example="08012345678"),
        ColumnSpec("gender", "Gender", example="M", choices=['M', 'F', 'O']),
        ColumnSpec("reg_number", "Registration Number", required=False, example="U22EE1001"),
        ColumnSpec("department", "Department", required=False, example="Mechanical Engineering"),
        ColumnSpec("campus_residence", "Campus Residence", required=False, example="Yes"),
        ColumnSpec("islamic_knowledge", "Islamic Knowledge", example="intermediate", choices=['beginner', 'intermediate', 'advanced']),
        ColumnSpec("quran_memorization", "Quran Memorization", required=False, example="some", choices=['none', 'some', 'half', 'whole']),
        ColumnSpec("how_work_with_people", "How Work With People", required=False, example="I enjoy helping others..."),
        ColumnSpec("recommendations", "Recommendations", required=False, example="Dr. Ahmed, Prof. Bello"),
        ColumnSpec("other_skill", "Other Skill", required=False, example="Public Speaking"),
        ColumnSpec("skills", "Skills (comma separated)", required=False, example="Programming,Graphic Design"),
    ]

    def validate_row(self, row):
        errors = super().validate_row(row)

        # Validate email uniqueness
        email = row.get("email", "").strip()
        if email and MembershipApplication.objects.filter(email__iexact=email).exists():
            errors.append(f"Email '{email}' already exists.")

        # Validate gender
        gender = row.get("gender", "").strip().upper()
        if gender and gender not in ['M', 'F', 'O']:
            errors.append(f"Gender must be M, F, or O. Got '{gender}'.")

        return errors

    def build_instance(self, row):
        # Parse skills (comma separated)
        skill_names = [s.strip() for s in row.get("skills", "").split(',') if s.strip()]
        skills = []
        for name in skill_names:
            skill, _ = Skill.objects.get_or_create(name=name, defaults={'is_active': True})
            skills.append(skill)

        app = MembershipApplication.objects.create(
            name=row.get("name", "").strip(),
            email=row.get("email", "").strip(),
            phone=row.get("phone", "").strip(),
            gender=row.get("gender", "").strip().upper(),
            reg_number=row.get("reg_number", "").strip(),
            department=row.get("department", "").strip(),
            campus_residence=row.get("campus_residence", "").strip().lower() in ("yes", "true", "1"),
            islamic_knowledge=row.get("islamic_knowledge", "beginner").strip().lower(),
            quran_memorization=row.get("quran_memorization", "none").strip().lower(),
            how_work_with_people=row.get("how_work_with_people", "").strip(),
            recommendations=row.get("recommendations", "").strip(),
            other_skill=row.get("other_skill", "").strip(),
            is_processed=False,
        )
        app.skills.set(skills)
        return app


# Register the spec
register(MembershipImportSpec())



