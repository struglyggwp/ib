# Обновление Security Awareness Platform v0.16 → v0.17

Версия v0.17 убирает отдельный пользовательский конструктор сценариев и обязательную DNS TXT-проверку. Теперь **кампания** объединяет письмо, сотрудников, запуск и отчёт.

## Перед обновлением

1. **Не удаляйте Docker volumes.** Команда `docker compose down -v` опасна для базы.
2. Узнайте имя текущего Docker Compose-проекта:

```powershell
cd C:\security_awareness_platform_v0_16
docker compose ls
```

3. Сохраните актуальное имя проекта (пример ниже, замените на своё):

```powershell
$project = "security_awareness_platform_v0_15"
cmd /c "docker compose -p $project exec -T db pg_dump -U awareness awareness > backup_v016.sql"
Get-Item .\backup_v016.sql | Select-Object Name,Length
```

Если `Length` равен нулю, исправьте резервное копирование до обновления.

## Установка

Распакуйте ZIP в `C:\security_awareness_platform_v0_17`.

```powershell
Copy-Item C:\security_awareness_platform_v0_16\.env C:\security_awareness_platform_v0_17\.env
cd C:\security_awareness_platform_v0_17
# Только если прежний Compose-проект ещё работает:
# docker compose -p $project down
# Запускаем новую версию на прежних volumes:
docker compose -p $project --profile mailtest up -d --build
```

Если старая v0.16 уже остановлена, строку `down` не выполняйте. Чтобы использовать абсолютно новую БД, а не старые тома, запускайте без `-p`, но тогда старые данные автоматически не появятся.

## Настройка SMTP

Тестовый режим Mailpit:

```env
SMTP_HOST=mailpit
SMTP_PORT=1025
SMTP_USE_STARTTLS=0
SMTP_USE_SSL=0
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=training@training.test
SMTP_CAMPAIGN_ENABLED=1
SMTP_ALLOWED_RECIPIENT_DOMAINS=training.test
SIMULATION_LOCAL_BASE_URL=http://127.0.0.1:8080
```

Для настоящей внутренней Zimbra в `.env` задайте её `SMTP_HOST`, `SMTP_PORT=587`, `SMTP_USE_STARTTLS=1`, реальный `SMTP_USERNAME`, `SMTP_PASSWORD` и `SMTP_FROM_EMAIL` с **тем же адресом**, что в `SMTP_USERNAME`. Отдельный публичный TXT не требуется. Получатели ограничены `SMTP_ALLOWED_RECIPIENT_DOMAINS`; учебные ссылки для Zimbra требуют внутренний HTTPS-адрес `SIMULATION_PUBLIC_BASE_URL` и соответствующий `SIMULATION_ALLOWED_LINK_HOSTS`.

После редактирования `.env` пересоздайте web и worker:

```powershell
docker compose -p $project --profile mailtest up -d --force-recreate web worker
```

## Проверка

```powershell
docker compose -p $project ps
docker compose -p $project exec web python manage.py check
docker compose -p $project exec web python manage.py makemigrations --check --dry-run
docker compose -p $project exec web python manage.py test
docker compose -p $project logs --tail=100 web worker
```

Откройте http://127.0.0.1:8080/campaigns/ : **Новая кампания → письмо и участники → Сохранить → Запустить**. Ссылки и журнал отправки создаются автоматически. Страница `/scenarios/` перенаправляет к списку кампаний.

## Что происходит со старыми сценариями

Миграция `campaigns.0005_import_unused_scenarios` создаёт черновики кампаний для сценариев, которые ещё не имели связанной кампании. Уже запущенные сценарии представлены связанными кампаниями; данные истории и связи в таблицах сохраняются. Сами исторические таблицы не удалены намеренно, чтобы не потерять данные при обновлении.

## Границы проверки

ZIP проходит статическую проверку кода и целостности, но в среде сборки нет работающего Django/Docker стенда. `manage.py test`, реальную отправку и миграцию на ваших данных необходимо проверить после установки.
