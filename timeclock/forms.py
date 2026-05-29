from django import forms
from django.utils.translation import gettext_lazy as _

from .models import AbsenceRecord, Employee, PunchRecord


class EmployeeForm(forms.ModelForm):
    face_descriptor_json = forms.CharField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = Employee
        fields = ['name', 'cpf', 'email', 'photo', 'daily_hours', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'cpf': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '000.000.000-00'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'daily_hours': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.5'}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        descriptor_json = self.cleaned_data.get('face_descriptor_json')
        if descriptor_json:
            import json
            try:
                instance.face_descriptor = json.loads(descriptor_json)
            except (ValueError, TypeError):
                pass
        if commit:
            instance.save()
        return instance


class PunchEditForm(forms.ModelForm):
    punched_at = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
        input_formats=['%Y-%m-%dT%H:%M'],
    )

    class Meta:
        model = PunchRecord
        fields = ['employee', 'punch_type', 'punched_at', 'manual_reason']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-input'}),
            'punch_type': forms.Select(attrs={'class': 'form-input'}),
            'manual_reason': forms.TextInput(attrs={'class': 'form-input'}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.is_manual = True
        if commit:
            instance.save()
        return instance


class AbsenceForm(forms.ModelForm):
    class Meta:
        model = AbsenceRecord
        fields = ['employee', 'date', 'hours_absent', 'reason', 'attachment']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-input'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'hours_absent': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.5'}),
            'reason': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }


class ReportFilterForm(forms.Form):
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.filter(is_active=True),
        required=False,
        empty_label=_('Todos os funcionários'),
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
    )
