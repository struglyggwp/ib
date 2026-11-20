**Версия 0.19** · [Два HTML-шаблона, адреса отправителя и настройка Zimbra](docs/V019.md)

# Security Awareness Platform v0.18 — учёт сигналов открытия писем

Создай кампанию → выбери HTML-шаблон и сотрудников → запусти → смотри сигналы загрузки изображения, переходы и завершение.

Новая возможность не гарантирует, что сотрудник действительно прочитал письмо: картинку могут блокировать или загрузить автоматически.

**Инструкция обновления и тестирования:** `docs/UPGRADE_V0_17_TO_V0_18.md`.

# Security Awareness Platform v0.17 — без сценариев и DNS TXT

Одна рабочая сущность: **кампания**. Создать → выбрать шаблон и сотрудников → сохранить → **Запустить** → смотреть отчёт. Отдельный конструктор сценариев, этапы, проверка готовности и DNS TXT-подтверждение в интерфейсе удалены.

## Безопасное обновление с v0.16

Сохраняйте имя Compose-проекта, с которым создавалась база, и старый `.env`. Например:

```powershell
cd C:\security_awareness_platform_v0_16
$project = "security_awareness_platform_v0_15" # ЗАМЕНИТЕ на значение из docker compose ls
cmd /c "docker compose -p $project exec -T db pg_dump -U awareness awareness > backup_v016.sql"
Get-Item .\backup_v016.sql | Select-Object Name,Length
# Распакуйте архив в C:\security_awareness_platform_v0_17
Copy-Item .\.env C:\security_awareness_platform_v0_17\.env
cd C:\security_awareness_platform_v0_17
docker compose -p $project --profile mailtest up -d --build
```

Никакого `down -v`: он может удалить БД. Миграция `campaigns.0005` переносит неиспользованные старые сценарии в черновики кампаний; историю сценариев и прошлые связи не стирает. Если БД новая, автоматические миграции создадут её сами.

## SMTP

Для локального Mailpit:

```env
SMTP_HOST=mailpit
SMTP_PORT=1025
SMTP_USE_STARTTLS=0
SMTP_USE_SSL=0
SMTP_FROM_EMAIL=training@training.test
SMTP_CAMPAIGN_ENABLED=1
SMTP_ALLOWED_RECIPIENT_DOMAINS=training.test
SIMULATION_LOCAL_BASE_URL=http://127.0.0.1:8080
```

Mailpit: http://127.0.0.1:8025/. Используйте тестовые email в зоне `.test`.

Для собственной Zimbra:

```env
SMTP_HOST=mail.internal.example
SMTP_PORT=587
SMTP_USE_STARTTLS=1
SMTP_USE_SSL=0
SMTP_USERNAME=training@your-internal-mail.example
SMTP_PASSWORD=YOUR_MAILBOX_PASSWORD
SMTP_FROM_EMAIL=training@your-internal-mail.example
SMTP_CAMPAIGN_ENABLED=1
SMTP_ALLOWED_RECIPIENT_DOMAINS=your-internal-mail.example
SIMULATION_PUBLIC_BASE_URL=https://training.your-internal-mail.example
SIMULATION_ALLOWED_LINK_HOSTS=training.your-internal-mail.example
```

Замените демонстрационные хосты на свои. Публичный TXT не используется; отправитель должен быть тем же аутентифицированным почтовым ящиком Zimbra. Внутренний HTTPS-адрес учебной ссылки должен быть доступен сотрудникам. Отправка ограничена доменами получателей и скоростью, без автоматических повторов неоднозначных SMTP-ошибок.

## Проверки

```powershell
docker compose -p $project exec web python manage.py check
docker compose -p $project exec web python manage.py makemigrations --check --dry-run
docker compose -p $project exec web python manage.py test
docker compose -p $project logs --tail=100 web
```

Интерфейс: http://127.0.0.1:8080/campaigns/ . История старых сценариев остаётся в БД для совместимости; их URL перенаправляются на кампании. Доставка SMTP не равна гарантированному получению. Уникальная ссылка связывает событие с адресатом, а не гарантирует личность человека, открывшего ссылку.
