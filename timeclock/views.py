import json
import traceback
from datetime import date, datetime, timedelta

import numpy as np
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .balance import format_timedelta, get_period_balance
from .forms import AbsenceForm, EmployeeForm, PunchEditForm, ReportFilterForm
from .models import AbsenceRecord, Employee, PunchRecord, next_expected_punch


# ---------------------------------------------------------------------------
# Public — punch terminal
# ---------------------------------------------------------------------------

def punch_terminal(request):
    return render(request, 'timeclock/punch_terminal.html')


@require_POST
def api_punch(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'invalid_json'}, status=400)

    descriptor = data.get('descriptor')
    override_type = data.get('override_type')

    # Fix: guard against non-list before calling len()
    if not isinstance(descriptor, list) or len(descriptor) != 128:
        return JsonResponse({'error': 'invalid_descriptor', 'detail': f'got {len(descriptor) if isinstance(descriptor, list) else type(descriptor).__name__}, expected list[128]'}, status=400)

    # Fix: validate override_type against known choices before hitting the DB
    if override_type is not None:
        _valid = {k for k, _ in PunchRecord.PUNCH_TYPES}
        if override_type not in _valid:
            return JsonResponse({'error': 'invalid_punch_type', 'detail': f'must be one of {sorted(_valid)}'}, status=400)

    try:
        employee, confidence = _find_employee(descriptor)
    except Exception as e:
        traceback.print_exc()
        # Fix: only expose detail in DEBUG to avoid leaking internals in production
        detail = str(e) if settings.DEBUG else 'Internal error'
        return JsonResponse({'error': 'find_employee_failed', 'detail': detail}, status=500)

    if employee is None:
        return JsonResponse({'error': 'face_not_recognized', 'confidence': confidence}, status=404)

    now = timezone.now()
    today = now.astimezone(timezone.get_current_timezone()).date()

    if override_type:
        punch_type = override_type
    else:
        punch_type = next_expected_punch(employee, today)
        if punch_type is None:
            return JsonResponse({'error': 'all_punches_done', 'detail': 'Todas as batidas do dia já registradas.'}, status=409)

    punch = PunchRecord.objects.create(
        employee=employee,
        punch_type=punch_type,
        punched_at=now,
        face_confidence=confidence,
    )

    local_time = now.astimezone(timezone.get_current_timezone())
    return JsonResponse({
        'employee_id': employee.id,
        'employee_name': employee.name,
        'punch_type': punch_type,
        'punch_type_label': punch.get_punch_type_label(),
        'punched_at': local_time.strftime('%H:%M'),
        'confidence': round(confidence, 3),
    })


def _find_employee(descriptor):
    threshold = getattr(settings, 'FACE_CONFIDENCE_THRESHOLD', 0.60)
    query = np.array(descriptor, dtype=np.float32)
    query_norm = np.linalg.norm(query)
    if query_norm == 0:
        return None, 0.0

    best_score = 0.0
    best_employee = None

    for emp in Employee.objects.filter(is_active=True, face_descriptor__isnull=False):
        ref = np.array(emp.face_descriptor, dtype=np.float32)
        ref_norm = np.linalg.norm(ref)
        if ref_norm == 0:
            continue
        score = float(np.dot(query, ref) / (query_norm * ref_norm))
        if score > best_score:
            best_score = score
            best_employee = emp

    if best_score >= threshold:
        return best_employee, best_score
    return None, best_score


# ---------------------------------------------------------------------------
# Admin — dashboard
# ---------------------------------------------------------------------------

@login_required
@staff_member_required
def admin_dashboard(request):
    today = timezone.localdate()
    today_punches = PunchRecord.objects.filter(punched_at__date=today).select_related('employee')

    clocked_in = set()
    on_lunch = set()
    clocked_out = set()

    for p in today_punches.order_by('punched_at'):
        if p.punch_type == 'clock_in':
            clocked_in.add(p.employee_id)
        elif p.punch_type == 'lunch_start':
            on_lunch.add(p.employee_id)
        elif p.punch_type == 'lunch_end':
            on_lunch.discard(p.employee_id)
        elif p.punch_type == 'clock_out':
            clocked_out.add(p.employee_id)
            clocked_in.discard(p.employee_id)

    active_count = Employee.objects.filter(is_active=True).count()
    present_ids = clocked_in | clocked_out
    absent_count = active_count - len(present_ids)

    recent_punches = today_punches.order_by('-punched_at')[:10]

    return render(request, 'timeclock/admin/dashboard.html', {
        'active_count': active_count,
        'present_count': len(present_ids),
        'on_lunch_count': len(on_lunch),
        'clocked_out_count': len(clocked_out),
        'absent_count': max(absent_count, 0),
        'recent_punches': recent_punches,
        'today': today,
    })


# ---------------------------------------------------------------------------
# Admin — employees
# ---------------------------------------------------------------------------

@login_required
@staff_member_required
def employee_list(request):
    employees = Employee.objects.all()
    return render(request, 'timeclock/admin/employees.html', {'employees': employees})


@login_required
@staff_member_required
def employee_create(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, _('Funcionário cadastrado com sucesso.'))
            return redirect('employee_list')
    else:
        form = EmployeeForm()
    return render(request, 'timeclock/admin/employee_form.html', {'form': form, 'action': _('Cadastrar')})


@login_required
@staff_member_required
def employee_edit(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, _('Funcionário atualizado.'))
            return redirect('employee_list')
    else:
        form = EmployeeForm(instance=employee)
    return render(request, 'timeclock/admin/employee_form.html', {
        'form': form,
        'employee': employee,
        'action': _('Atualizar'),
    })


@login_required
@staff_member_required
def employee_delete(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        employee.is_active = False
        employee.save()
        messages.success(request, _('Funcionário desativado.'))
        return redirect('employee_list')
    return render(request, 'timeclock/admin/employee_confirm_delete.html', {'employee': employee})


# ---------------------------------------------------------------------------
# Admin — punches
# ---------------------------------------------------------------------------

@login_required
@staff_member_required
def punch_list(request):
    qs = PunchRecord.objects.select_related('employee').order_by('-punched_at')
    employee_id = request.GET.get('employee')
    date_str = request.GET.get('date')

    if employee_id:
        qs = qs.filter(employee_id=employee_id)
    if date_str:
        try:
            filter_date = date.fromisoformat(date_str)
            qs = qs.filter(punched_at__date=filter_date)
        except ValueError:
            pass

    employees = Employee.objects.filter(is_active=True)
    return render(request, 'timeclock/admin/punch_list.html', {
        'punches': qs[:200],
        'employees': employees,
        'selected_employee': employee_id,
        'selected_date': date_str,
    })


@login_required
@staff_member_required
def punch_edit(request, pk):
    punch = get_object_or_404(PunchRecord, pk=pk)
    if request.method == 'POST':
        form = PunchEditForm(request.POST, instance=punch)
        if form.is_valid():
            form.save()
            messages.success(request, _('Registro atualizado.'))
            return redirect('punch_list')
    else:
        initial_dt = punch.punched_at.astimezone(timezone.get_current_timezone())
        form = PunchEditForm(instance=punch, initial={
            'punched_at': initial_dt.strftime('%Y-%m-%dT%H:%M')
        })
    return render(request, 'timeclock/admin/punch_form.html', {'form': form, 'punch': punch})


@login_required
@staff_member_required
def punch_create(request):
    if request.method == 'POST':
        form = PunchEditForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _('Batida registrada manualmente.'))
            return redirect('punch_list')
    else:
        form = PunchEditForm()
    return render(request, 'timeclock/admin/punch_form.html', {'form': form})


@login_required
@staff_member_required
def punch_delete(request, pk):
    punch = get_object_or_404(PunchRecord, pk=pk)
    if request.method == 'POST':
        punch.delete()
        messages.success(request, _('Registro removido.'))
        return redirect('punch_list')
    return render(request, 'timeclock/admin/punch_confirm_delete.html', {'punch': punch})


# ---------------------------------------------------------------------------
# Admin — absences
# ---------------------------------------------------------------------------

@login_required
@staff_member_required
def absence_list(request):
    absences = AbsenceRecord.objects.select_related('employee', 'approved_by').order_by('-date')
    return render(request, 'timeclock/admin/absences.html', {'absences': absences})


@login_required
@staff_member_required
def absence_create(request):
    if request.method == 'POST':
        form = AbsenceForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, _('Abono registrado.'))
            return redirect('absence_list')
    else:
        form = AbsenceForm()
    return render(request, 'timeclock/admin/absence_form.html', {'form': form})


@login_required
@staff_member_required
def absence_approve(request, pk):
    absence = get_object_or_404(AbsenceRecord, pk=pk)
    absence.approved_by = request.user
    absence.approved_at = timezone.now()
    absence.save()
    messages.success(request, _('Abono aprovado.'))
    return redirect('absence_list')


@login_required
@staff_member_required
def absence_delete(request, pk):
    absence = get_object_or_404(AbsenceRecord, pk=pk)
    if request.method == 'POST':
        absence.delete()
        messages.success(request, _('Abono removido.'))
        return redirect('absence_list')
    return render(request, 'timeclock/admin/absence_confirm_delete.html', {'absence': absence})


# ---------------------------------------------------------------------------
# Admin — balance
# ---------------------------------------------------------------------------

@login_required
@staff_member_required
def balance_view(request):
    today = timezone.localdate()
    first_of_month = today.replace(day=1)

    employee_id = request.GET.get('employee')
    start_str = request.GET.get('start', first_of_month.isoformat())
    end_str = request.GET.get('end', today.isoformat())

    try:
        start_date = date.fromisoformat(start_str)
        end_date = date.fromisoformat(end_str)
    except ValueError:
        start_date, end_date = first_of_month, today

    employees = Employee.objects.filter(is_active=True)
    selected_employee = None
    balance_data = None

    if employee_id:
        selected_employee = get_object_or_404(Employee, pk=employee_id)
        balance_data = get_period_balance(selected_employee, start_date, end_date)
        balance_data['formatted'] = [
            {
                **row,
                'worked_fmt': format_timedelta(row['worked']),
                'expected_fmt': format_timedelta(row['expected']),
                'balance_fmt': format_timedelta(row['balance']),
            }
            for row in balance_data['rows']
        ]
        balance_data['total_worked_fmt'] = format_timedelta(balance_data['total_worked'])
        balance_data['total_expected_fmt'] = format_timedelta(balance_data['total_expected'])
        balance_data['total_balance_fmt'] = format_timedelta(balance_data['total_balance'])

    return render(request, 'timeclock/admin/balance.html', {
        'employees': employees,
        'selected_employee': selected_employee,
        'start_date': start_date,
        'end_date': end_date,
        'balance_data': balance_data,
    })


# ---------------------------------------------------------------------------
# Admin — reports
# ---------------------------------------------------------------------------

@login_required
@staff_member_required
def reports_view(request):
    form = ReportFilterForm(request.GET or None)
    report_data = None

    if form.is_valid():
        employee = form.cleaned_data.get('employee')
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']

        if employee:
            employees_qs = [employee]
        else:
            employees_qs = Employee.objects.filter(is_active=True)

        report_data = []
        for emp in employees_qs:
            bd = get_period_balance(emp, start_date, end_date)
            bd['employee'] = emp
            bd['total_worked_fmt'] = format_timedelta(bd['total_worked'])
            bd['total_balance_fmt'] = format_timedelta(bd['total_balance'])
            for row in bd['rows']:
                row['worked_fmt'] = format_timedelta(row['worked'])
                row['balance_fmt'] = format_timedelta(row['balance'])
            report_data.append(bd)

    return render(request, 'timeclock/admin/reports.html', {
        'form': form,
        'report_data': report_data,
    })


@login_required
@staff_member_required
def report_pdf(request):
    employee_id = request.GET.get('employee')
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')

    try:
        start_date = date.fromisoformat(start_str)
        end_date = date.fromisoformat(end_str)
    except (TypeError, ValueError):
        return HttpResponse('Parâmetros inválidos', status=400)

    if employee_id:
        employees_qs = [get_object_or_404(Employee, pk=employee_id)]
    else:
        employees_qs = Employee.objects.filter(is_active=True)

    report_data = []
    for emp in employees_qs:
        bd = get_period_balance(emp, start_date, end_date)
        bd['employee'] = emp
        bd['total_worked_fmt'] = format_timedelta(bd['total_worked'])
        bd['total_balance_fmt'] = format_timedelta(bd['total_balance'])
        for row in bd['rows']:
            row['worked_fmt'] = format_timedelta(row['worked'])
            row['balance_fmt'] = format_timedelta(row['balance'])
        report_data.append(bd)

    html = render_to_string('reports/monthly_report.html', {
        'report_data': report_data,
        'start_date': start_date,
        'end_date': end_date,
        'company_name': 'Centraltur Viagens',
    }, request=request)

    from weasyprint import HTML
    pdf = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()

    period_label = f'{start_date.strftime("%Y%m%d")}-{end_date.strftime("%Y%m%d")}'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="relatorio_{period_label}.pdf"'
    return response


@login_required
@staff_member_required
def report_send_email(request):
    if request.method != 'POST':
        return redirect('reports_view')

    employee_id = request.POST.get('employee')
    start_str = request.POST.get('start')
    end_str = request.POST.get('end')

    try:
        employee = get_object_or_404(Employee, pk=employee_id)
        start_date = date.fromisoformat(start_str)
        end_date = date.fromisoformat(end_str)
    except (TypeError, ValueError):
        messages.error(request, _('Parâmetros inválidos.'))
        return redirect('reports_view')

    bd = get_period_balance(employee, start_date, end_date)
    bd['employee'] = employee
    bd['total_worked_fmt'] = format_timedelta(bd['total_worked'])
    bd['total_balance_fmt'] = format_timedelta(bd['total_balance'])
    for row in bd['rows']:
        row['worked_fmt'] = format_timedelta(row['worked'])
        row['balance_fmt'] = format_timedelta(row['balance'])

    html = render_to_string('reports/monthly_report.html', {
        'report_data': [bd],
        'start_date': start_date,
        'end_date': end_date,
        'company_name': 'Centraltur Viagens',
    }, request=request)

    from weasyprint import HTML
    pdf = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()

    period_label = f'{start_date.strftime("%d/%m/%Y")} – {end_date.strftime("%d/%m/%Y")}'
    filename = f'relatorio_{start_date.strftime("%Y%m%d")}-{end_date.strftime("%Y%m%d")}.pdf'

    email = EmailMessage(
        subject=f'Relatório de Ponto — {period_label}',
        body=f'Olá {employee.name},\n\nSegue em anexo seu relatório de ponto referente ao período {period_label}.\n\nCentraltur Viagens',
        to=[employee.email],
    )
    email.attach(filename, pdf, 'application/pdf')
    email.send()

    messages.success(request, _('Relatório enviado para %(email)s.') % {'email': employee.email})
    return redirect('reports_view')
