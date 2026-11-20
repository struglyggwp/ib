from django import forms
from .models import Employee


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ("last_name", "first_name", "middle_name", "email", "department", "position", "is_active")
        widgets = {
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "middle_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "position": forms.Select(attrs={"class": "form-select"}),
        }


class CSVImportForm(forms.Form):
    file = forms.FileField(label="CSV-файл", widget=forms.FileInput(attrs={"class": "form-control", "accept": ".csv,text/csv"}))

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if uploaded.size > 2 * 1024 * 1024:
            raise forms.ValidationError("Размер файла не должен превышать 2 МБ.")
        if not uploaded.name.lower().endswith(".csv"):
            raise forms.ValidationError("Загрузите файл с расширением .csv.")
        return uploaded
