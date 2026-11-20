import csv
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import CSVImportForm, EmployeeForm
from .models import Department, Employee, Position


@login_required
def employee_list(request):
    qs = Employee.objects.select_related("department", "position")
    query = request.GET.get("q", "").strip()
    department = request.GET.get("department", "").strip()
    status = request.GET.get("status", "").strip()
    if query:
        qs = qs.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(middle_name__icontains=query) | Q(email__icontains=query))
    if department.isdigit():
        qs = qs.filter(department_id=int(department))
    if status in ("active", "inactive"):
        qs = qs.filter(is_active=(status == "active"))
    return render(request, "employees/list.html", {
        "employees": qs, "query": query, "selected_department": department,
        "selected_status": status, "departments": Department.objects.filter(is_active=True),
    })


@login_required
@require_http_methods(["GET", "POST"])
def employee_create(request):
    form = EmployeeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        employee = form.save()
        messages.success(request, "Сотрудник добавлен в каталог.")
        return redirect("employee_detail", employee_id=employee.pk)
    return render(request, "employees/form.html", {"form": form, "page_title": "Новый сотрудник"})


@login_required
@require_http_methods(["GET", "POST"])
def employee_edit(request, employee_id):
    employee = get_object_or_404(Employee, pk=employee_id)
    form = EmployeeForm(request.POST or None, instance=employee)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Данные сотрудника обновлены.")
        return redirect("employee_detail", employee_id=employee.pk)
    return render(request, "employees/form.html", {"form": form, "page_title": "Изменить сотрудника", "employee": employee})


@login_required
def employee_detail(request, employee_id):
    employee = get_object_or_404(Employee.objects.select_related("department", "position"), pk=employee_id)
    return render(request, "employees/detail.html", {"employee": employee})


@login_required
@require_http_methods(["GET", "POST"])
def csv_import(request):
    form = CSVImportForm(request.POST or None, request.FILES or None)
    preview = None
    errors = []
    if request.method == "POST" and form.is_valid():
        raw = form.cleaned_data["file"].read()
        try:
            try:
                content = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                content = raw.decode("cp1251")
        except UnicodeDecodeError:
            content = ""
            errors.append("Не удалось определить кодировку CSV. Используйте UTF-8 или Windows-1251.")
        first_line = content.splitlines()[0] if content.splitlines() else ""
        reader = csv.DictReader(io.StringIO(content, newline=""), delimiter=";" if first_line.count(";") > first_line.count(",") else ",")
        required = {"first_name", "last_name", "email"}
        headers = set(reader.fieldnames or [])
        if not required.issubset(headers):
            errors.append("Обязательные заголовки: first_name, last_name, email. Дополнительно: middle_name, department, position, is_active.")
        else:
            rows = []
            seen = set()
            for line_no, row in enumerate(reader, start=2):
                email = (row.get("email") or "").strip().lower()
                first = (row.get("first_name") or "").strip()
                last = (row.get("last_name") or "").strip()
                if not email or not first or not last:
                    errors.append(f"Строка {line_no}: не заполнены first_name, last_name или email.")
                    continue
                try:
                    validate_email(email)
                except ValidationError:
                    errors.append(f"Строка {line_no}: некорректный email {email}.")
                    continue
                if email in seen or Employee.objects.filter(email__iexact=email).exists():
                    errors.append(f"Строка {line_no}: адрес {email} повторяется или уже существует.")
                    continue
                seen.add(email)
                rows.append({"first_name": first, "last_name": last, "middle_name": (row.get("middle_name") or "").strip(), "email": email,
                             "department": (row.get("department") or "").strip(), "position": (row.get("position") or "").strip(),
                             "is_active": (row.get("is_active") or "true").strip().lower() not in ("0", "false", "no", "нет")})
            if not rows and not errors:
                errors.append("В CSV-файле нет строк для импорта.")
            if not errors:
                try:
                    with transaction.atomic():
                        for row in rows:
                            dept_name, pos_name = row.pop("department"), row.pop("position")
                            dept = Department.objects.filter(name__iexact=dept_name).first() if dept_name else None
                            pos = Position.objects.filter(name__iexact=pos_name).first() if pos_name else None
                            if dept_name and dept is None:
                                dept = Department.objects.create(name=dept_name)
                            if pos_name and pos is None:
                                pos = Position.objects.create(name=pos_name)
                            Employee.objects.create(**row, department=dept, position=pos)
                    messages.success(request, f"Импортировано сотрудников: {len(rows)}.")
                    return redirect("employee_list")
                except IntegrityError:
                    errors.append("Импорт отменён: обнаружен конфликт данных. Проверьте уникальность адресов и повторите попытку.")
        preview = {"count": 0, "errors": errors}
    return render(request, "employees/import.html", {"form": form, "preview": preview})
