from datetime import timedelta

from django.utils import timezone

from .models import PunchRecord


def calculate_day_balance(employee, date):
    punches = PunchRecord.objects.filter(
        employee=employee,
        punched_at__date=date,
    ).order_by('punched_at')

    clock_in = punches.filter(punch_type='clock_in').first()
    clock_out = punches.filter(punch_type='clock_out').first()
    l_start = punches.filter(punch_type='lunch_start').first()
    l_end = punches.filter(punch_type='lunch_end').first()

    if not clock_in:
        return None

    worked = None
    if clock_out:
        worked = clock_out.punched_at - clock_in.punched_at
        if l_start and l_end:
            worked -= l_end.punched_at - l_start.punched_at

    expected = timedelta(hours=float(employee.daily_hours))

    balance = None
    if worked is not None:
        balance = worked - expected

    return {
        'date': date,
        'clock_in': clock_in,
        'lunch_start': l_start,
        'lunch_end': l_end,
        'clock_out': clock_out,
        'worked': worked,
        'expected': expected,
        'balance': balance,
    }


def format_timedelta(td):
    if td is None:
        return '—'
    total_seconds = int(td.total_seconds())
    sign = '-' if total_seconds < 0 else ''
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    return f'{sign}{hours:02d}:{minutes:02d}'


def get_period_balance(employee, start_date, end_date):
    from datetime import date as date_type
    rows = []
    current = start_date
    total_worked = timedelta()
    total_expected = timedelta()
    total_balance = timedelta()

    while current <= end_date:
        day = calculate_day_balance(employee, current)
        if day:
            rows.append(day)
            if day['worked']:
                total_worked += day['worked']
            total_expected += day['expected']
            if day['balance']:
                total_balance += day['balance']
        current += timedelta(days=1)

    return {
        'rows': rows,
        'total_worked': total_worked,
        'total_expected': total_expected,
        'total_balance': total_balance,
    }
