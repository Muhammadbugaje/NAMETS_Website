from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .registry import IMPORT_REGISTRY
from .excel_io import (
    build_template_xlsx,
    read_uploaded_rows,
    build_export_xlsx,
    UploadTooLarge,
)
from .models import PendingImportBatch


def _check_spec_access(user, spec):
    """
    Check if user can access this import spec.
    - Superusers always allowed.
    - If spec has required_offices, user must hold one of those offices.
    - Otherwise, user must be staff (is_staff).
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    required_offices = getattr(spec, 'required_offices', None)
    if required_offices:
        return user.office_assignments.filter(
            office__name__in=required_offices, is_active=True
        ).exists()
    return user.is_staff


@login_required
def download_template(request, import_key):
    spec = IMPORT_REGISTRY[import_key]
    if not _check_spec_access(request.user, spec):
        raise PermissionDenied
    return build_template_xlsx(spec)



@login_required
def upload_review(request, import_key):
    spec = IMPORT_REGISTRY[import_key]
    if not _check_spec_access(request.user, spec):
        raise PermissionDenied

    PendingImportBatch.clean_expired()

    form_params = {}
    evaluations = None  # only used for results

    # Only fetch Evaluation objects for the results importer
    if import_key == "results":
        from academics.models import Evaluation  # import here to avoid global ImportError
        evaluation_id = request.GET.get('evaluation_id') or request.POST.get('evaluation_id')
        if evaluation_id:
            try:
                evaluation = Evaluation.objects.get(id=evaluation_id)
                form_params['evaluation'] = evaluation
            except Evaluation.DoesNotExist:
                messages.error(request, "Selected evaluation does not exist.")
                return redirect('importers:upload', import_key=import_key)
        else:
            messages.error(request, "Please select an evaluation first.")
            return redirect('importers:upload', import_key=import_key)

        evaluations = Evaluation.objects.all().order_by('-date')

    if request.method == 'POST' and request.FILES.get('excel_file'):
        try:
            rows, missing_headers = read_uploaded_rows(request.FILES['excel_file'], spec)
        except UploadTooLarge as e:
            messages.error(request, str(e))
            return redirect('importers:upload', import_key=import_key)

        if missing_headers:
            messages.error(
                request,
                f"These required columns weren't found: {', '.join(missing_headers)}. "
                "Download the template again and check your column headers match exactly."
            )
            return redirect('importers:upload', import_key=import_key)

        valid_rows = []
        row_errors = []
        for row in rows:
            errors = spec.validate_row(row['data'], form_params=form_params)
            if errors:
                row_errors.append({'row_number': row['row_number'], 'errors': errors})
            else:
                valid_rows.append(row)

        batch = PendingImportBatch.objects.create(
            import_key=import_key,
            valid_rows=valid_rows,
            created_by=request.user,
            extra_data=form_params,
        )

        ai_summary = ''
        try:
            from .ai_summary import summarize_import_errors
            if row_errors:
                ai_summary = summarize_import_errors(row_errors)
        except ImportError:
            pass

        return render(request, 'importers/review.html', {
            'spec': spec,
            'batch': batch,
            'valid_count': len(valid_rows),
            'row_errors': row_errors,
            'ai_summary': ai_summary,
            'form_params': form_params,
        })

    # GET — show upload form with evaluation dropdown (only for results)
    return render(request, 'importers/upload.html', {
        'spec': spec,
        'evaluations': evaluations,  # None for other import keys
        'import_key': import_key,
    })


@login_required
def confirm_import(request, import_key, token):
    spec = IMPORT_REGISTRY[import_key]
    if not _check_spec_access(request.user, spec):
        raise PermissionDenied

    batch = get_object_or_404(PendingImportBatch, token=token, import_key=import_key)

    if batch.is_expired():
        batch.delete()
        messages.error(request, "This review has expired — please upload the file again.")
        return redirect('importers:upload', import_key=import_key)

    if request.method == 'POST':
        created = 0
        failed = []
        for row in batch.valid_rows:
            try:
                spec.build_instance(row['data'], form_params=batch.extra_data)
                created += 1
            except Exception as e:
                failed.append(f"Row {row['row_number']}: {e}")
        batch.delete()
        return render(request, 'importers/done.html', {
            'spec': spec,
            'created': created,
            'failed': failed,
        })

    return render(request, 'importers/review.html', {
        'spec': spec,
        'batch': batch,
        'valid_count': len(batch.valid_rows),
        'row_errors': [],
        'form_params': batch.extra_data,
    })

@login_required
def export_view(request, import_key):
    spec = IMPORT_REGISTRY[import_key]
    if not _check_spec_access(request.user, spec):
        raise PermissionDenied
    return build_export_xlsx(spec)