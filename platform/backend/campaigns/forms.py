from django import forms
from django.db.models import Q

from email_templates.models import EmailTemplate
from employees.models import Department, Employee
from .models import Campaign


class CampaignForm(forms.ModelForm):
    employees = forms.ModelMultipleChoiceField(
        label="Сотрудники", queryset=Employee.objects.none(), required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": 9}),
        help_text="Выберите получателей напрямую (Ctrl для нескольких).",
    )
    departments = forms.ModelMultipleChoiceField(
        label="Подразделения", queryset=Department.objects.none(), required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": 5}),
        help_text="Необязательно. Все активные сотрудники выбранных подразделений добавятся автоматически.",
    )

    class Meta:
        model = Campaign
        fields = ("name", "description", "email_template", "employees", "departments")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Название учебной кампании"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "email_template": forms.Select(attrs={"class": "form-select"}),
        }
        labels = {"name": "Название", "description": "Описание", "email_template": "Шаблон учебного письма"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current = list(self.instance.participants.values_list("employee_id", flat=True)) if self.instance.pk and not self.instance._state.adding else []
        self.fields["employees"].queryset = Employee.objects.filter(Q(is_active=True) | Q(pk__in=current)).distinct().order_by("last_name", "first_name")
        self.fields["departments"].queryset = Department.objects.filter(is_active=True).order_by("name")
        self.fields["email_template"].queryset = EmailTemplate.objects.filter(
            Q(status=EmailTemplate.Status.ACTIVE) | Q(pk=self.instance.email_template_id)
        ).distinct().order_by("name")
        if self.instance.pk and not self.instance._state.adding:
            self.fields["employees"].initial = current

    def audience_ids(self):
        direct = set(self.cleaned_data["employees"].filter(is_active=True).values_list("pk", flat=True))
        departments = list(self.cleaned_data["departments"].values_list("pk", flat=True))
        if departments:
            direct.update(Employee.objects.filter(is_active=True, department_id__in=departments).values_list("pk", flat=True))
        return direct
