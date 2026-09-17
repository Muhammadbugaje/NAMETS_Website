"""
Base classes for the universal import/export framework.

Each importable data type (Results, Competition Results, Timetable — and
later EXCO, Inventory, Attendance) defines one ImportSpec subclass
describing its columns and how to turn a validated row into a saved model
instance. Everything else (the template download, the header-matched file
reading, the review screen, the export button) is written once in this package
and never duplicated per data type.
"""
from dataclasses import dataclass, field



@dataclass
class ColumnSpec:
    key: str  # dict key used internally, e.g. "student_name"
    header: str  # exact column header shown in the template/file, e.g. "Student Name"
    required: bool = True
    example: str = ""  # shown in the downloadable sample row
    choices: list = field(default_factory=list)  # optional — for a documented value like entry_type


class ImportSpec:
    """Subclass this once per importable data type."""

    key = ""  # url-safe identifier, e.g. "results" — used in the registry and URLs
    label = ""  # human-readable, e.g. "Evaluation Results"
    model = None
    columns: list[ColumnSpec] = []

    # Optional: restrict import/export access to specific offices
    required_offices = None  # e.g., ["ICT Head"] or ["Financial Secretary"]

    def validate_row(self, row: dict, form_params: dict = None) -> list[str]:
        """
        Validate a single row. form_params contains form-level data (e.g., evaluation_id).
        """
        errors = []
        for col in self.columns:
            if col.required and not str(row.get(col.key, '')).strip():
                errors.append(f"'{col.header}' is required.")
        return errors

    def build_instance(self, row: dict, form_params: dict = None):
        """Build a model instance from a row and form-level parameters."""
        raise NotImplementedError

    def export_queryset(self):
        """Optional — return the queryset this spec exports when the
        'Export to Excel' button is used against it. Defaults to every row
        of the model; override to filter (e.g. only active entries)."""
        return self.model.objects.all()

    def row_from_instance(self, instance) -> dict:
        """Optional — how one existing row maps back to export column
        values. Only needed if export is used for this spec."""
        raise NotImplementedError