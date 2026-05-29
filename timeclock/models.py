from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Employee(models.Model):
    name = models.CharField(max_length=100)
    cpf = models.CharField(max_length=14, unique=True)
    email = models.EmailField()
    photo = models.ImageField(upload_to='employees/', null=True, blank=True)
    face_descriptor = models.JSONField(null=True, blank=True)
    daily_hours = models.DecimalField(max_digits=4, decimal_places=2, default=8.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class PunchRecord(models.Model):
    PUNCH_TYPES = [
        ('clock_in', 'Entrada'),
        ('lunch_start', 'Início Almoço'),
        ('lunch_end', 'Fim Almoço'),
        ('clock_out', 'Saída'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='punches')
    punch_type = models.CharField(max_length=20, choices=PUNCH_TYPES)
    punched_at = models.DateTimeField(default=timezone.now)
    is_manual = models.BooleanField(default=False)
    manual_reason = models.CharField(max_length=255, blank=True)
    face_confidence = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['punched_at']
        indexes = [
            models.Index(fields=['employee', 'punched_at']),
        ]

    def __str__(self):
        return f'{self.employee.name} — {self.get_punch_type_display()} @ {self.punched_at:%d/%m/%Y %H:%M}'

    def get_punch_type_label(self):
        return dict(self.PUNCH_TYPES).get(self.punch_type, self.punch_type)


PUNCH_ORDER = ['clock_in', 'lunch_start', 'lunch_end', 'clock_out']


def next_expected_punch(employee, date):
    today_punches = PunchRecord.objects.filter(
        employee=employee,
        punched_at__date=date,
    ).order_by('punched_at').values_list('punch_type', flat=True)

    done = list(today_punches)
    for pt in PUNCH_ORDER:
        if pt not in done:
            return pt
    return None


class AbsenceRecord(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='absences')
    date = models.DateField()
    hours_absent = models.DecimalField(max_digits=4, decimal_places=2)
    reason = models.TextField()
    attachment = models.FileField(upload_to='atestados/', null=True, blank=True)
    approved_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_absences'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'{self.employee.name} — {self.date} ({self.hours_absent}h)'

    @property
    def is_approved(self):
        return self.approved_by is not None
