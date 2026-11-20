# Обновление v0.13 → v0.14-preview (PowerShell)

1. Найти имя прежнего Compose-проекта: `docker compose ls` (при необходимости просмотреть `docker volume ls`).
2. В текущем проекте v0.13 выполнить backup, заменив `<project>` на фактическое значение (например, `security_awareness_platform_v0_11`):

```powershell
cd C:\security_awareness_platform_v0_13
$project = 'security_awareness_platform_v0_11'
cmd /c "docker compose -p $project exec -T db pg_dump -U awareness awareness > backup_v013.sql"
Get-Item .\backup_v013.sql | Select-Object Name,Length
```

Если ваши `POSTGRES_USER` и `POSTGRES_DB` отличаются от `awareness`, замените их в команде. Сохраните backup за пределами проекта.

3. Распаковать ZIP в `C:\security_awareness_platform_v0_14_preview` и скопировать существующий `.env`:

```powershell
Copy-Item C:\security_awareness_platform_v0_13\.env C:\security_awareness_platform_v0_14_preview\.env
notepad C:\security_awareness_platform_v0_14_preview\.env
```

4. Добавить SMTP настройки из `docs/ZIMBRA_AND_TRACKING.md`, если нужен тест почты. Не менять ранее использованный `POSTGRES_PASSWORD`, если база сохранена. Далее:

```powershell
cd C:\security_awareness_platform_v0_14_preview
docker compose -p $project --profile mailtest up -d --build
docker compose -p $project exec web python manage.py check
docker compose -p $project exec web python manage.py makemigrations --check --dry-run
docker compose -p $project exec web python manage.py test
docker compose -p $project ps
```

`entrypoint.sh` автоматически выполняет `migrate`, включая `campaigns.0004`; обновление добавляет таблицы, не удаляет старые.

5. Откройте `http://127.0.0.1:8080/campaigns/` и нужную кампанию. Создайте учебные ссылки, поставьте кампании статус «Выполняется», скопируйте ссылку для тестового сотрудника, перейдите по ней и нажмите кнопку ознакомления. Проверьте именной отчёт и журнал.
6. Для проверки почты: `http://127.0.0.1:8080/campaigns/mail/`, Mailpit — `http://127.0.0.1:8025/`.

**Нельзя использовать `docker compose down -v` для обновления**. Проектное имя `-p` должно совпадать с исходным, иначе старая БД не будет подключена.

## Что НЕ реализовано

- Полноценная Zimbra в контейнере платформы (нужна отдельная VM или внешний сервер).
- Реальная массовая рассылка или расписания рассылки.
- Определение достоверного открытия письма или идентичности без аутентификации.
- Сбор паролей или содержимого форм.

## Smoke checks

- `check`, `makemigrations --check --dry-run`, `test`
- Права: обычный Django пользователь не видит именные отчёты.
- Переход по отозванному/просроченному токену возвращает 410, по неактивной кампании 403.
- GET переход фиксируется с `occurred_at`; POST без CSRF не принимается.
- Проверка SMTP не отправляет письмо; кнопка тестового письма отправляет только адресату из allowlist.
