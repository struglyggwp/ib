# Security Awareness Platform v0.15 → v0.16 (одна кнопка)

## Что изменено

**Основной процесс:** создать сценарий → выбрать активный шаблон и аудиторию → нажать **«▶ Запустить сценарий»** → открыть именной отчёт. Никаких обязательных этапов, подтверждений готовности или ручного создания кампании больше нет.

На сервере автоматически создаются отдельная кампания с зафиксированным списком адресатов, индивидуальные учебные ссылки, записи передачи SMTP и задание Celery. По каждой ссылке фиксируются дата и время обращения на стороне Django, без сбора паролей и заполненных форм.

Сохранены старые представления/модели/маршруты, включая редактор этапов для ранее созданных записей, старый ручной механизм кампаний и данные. **Новых миграций для v0.16 нет:** меняются только сервисы/шаблоны/тесты/настройки окружения.

Исправлена ошибка `select_for_update()` с `LEFT OUTER JOIN` у необязательного `email_template` в обработчиках сценариев и рассылки, которая могла приводить к HTTP 500.

Повторное нажатие в течение пяти минут или пока рассылка находится в очереди/выполняется возвращает прежнюю кампанию без новой очереди. После завершения можно повторить сценарий как отдельную кампанию. Автоматические повторы после неоднозначной ошибки SMTP отсутствуют.

## Обновление с сохранением PostgreSQL

**Текущая установка v0.15 у вас использовала имя Compose-проекта `security_awareness_platform_v0_15`.** Если оно изменилось, посмотрите `docker compose ls` и используйте реальное имя. **Не удаляйте тома данных и не выполняйте `down -v`.**

В Windows PowerShell:

```powershell
$project = 'security_awareness_platform_v0_15'
cd C:\security_awareness_platform_v0_15
# Копия БД; выполняйте в старой папке до остановки контейнеров
cmd /c "docker compose -p $project exec -T db pg_dump -U awareness awareness > backup_v015.sql"
Get-Item .\backup_v015.sql | Select-Object Name,Length
```

Убедитесь, что размер копии ненулевой, сохраните её отдельно. Распакуйте новую версию в `C:\security_awareness_platform_v0_16` (внутри сразу лежит `docker-compose.yml`), затем:

```powershell
Copy-Item C:\security_awareness_platform_v0_15\.env C:\security_awareness_platform_v0_16\.env
cd C:\security_awareness_platform_v0_15
docker compose -p $project down
cd C:\security_awareness_platform_v0_16
notepad .env
```

Сохраните прежний `POSTGRES_PASSWORD`, `DJANGO_SECRET_KEY` и остальные секреты. Убедитесь, что настройки SMTP и разрешённые адресаты заполнены. Далее:

```powershell
docker compose -p $project --profile mailtest up -d --build
docker compose -p $project --profile mailtest ps
docker compose -p $project exec web python manage.py check
docker compose -p $project exec web python manage.py makemigrations --check --dry-run
docker compose -p $project exec web python manage.py test
docker compose -p $project logs --tail=100 web worker
```

Если вы используете только Zimbra, `--profile mailtest` можно опустить. Появление новых пустых сотрудников/кампаний говорит о неверном **имени Compose-проекта**: проверьте `docker volume ls`, не удаляя старые данные.

## Быстрая проверка Mailpit

В `.env`:

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
SMTP_MAX_PER_CAMPAIGN=25
SMTP_MAX_PER_MINUTE=5
SIMULATION_LOCAL_BASE_URL=http://127.0.0.1:8080
```

После изменения `.env`:

```powershell
docker compose -p $project --profile mailtest up -d --force-recreate web worker mailpit
```

1. На http://127.0.0.1:8080/ создайте активный шаблон письма с темой и текстом.
2. Добавьте тестового сотрудника `tester@training.test` в каталоге сотрудников.
3. В `Сценарии → Новый` выберите шаблон и этого сотрудника. Этапы не нужны.
4. Нажмите **«▶ Запустить сценарий»**. Система автоматически заведёт `training.test` для Mailpit и откроет отчёт созданной кампании.
5. Письмо проверьте на http://127.0.0.1:8025/. Откройте уникальную ссылку на той же машине.
6. Обновите отчёт кампании: появится событие перехода и серверное время.

`SMTP_CAMPAIGN_ENABLED=1` нужно включать только после проверки доменов получателей. Само открытие URL не гарантирует, что ссылку открыл именно владелец почты: почтовые сканеры также могут посещать ссылки.

## Подключение существующей внутренней Zimbra

В `.env` (все адреса **примеры**; используйте собственные ящики, DNS и сертификаты):

```env
SMTP_HOST=mail.company.test
SMTP_PORT=587
SMTP_USE_STARTTLS=1
SMTP_USE_SSL=0
SMTP_USERNAME=training@company.test
SMTP_PASSWORD=PASSWORD_FROM_ZIMBRA
SMTP_FROM_EMAIL=training@company.test
SMTP_CAMPAIGN_ENABLED=1
SMTP_ALLOWED_RECIPIENT_DOMAINS=company.test
SMTP_AUTHORIZED_SENDER_DOMAINS=company.test
SMTP_MAX_PER_CAMPAIGN=25
SMTP_MAX_PER_MINUTE=5
SIMULATION_PUBLIC_BASE_URL=https://learn.company.test
SIMULATION_ALLOWED_LINK_HOSTS=learn.company.test
```

`SMTP_AUTHORIZED_SENDER_DOMAINS` разрешает **только явно перечисленный домен**, причём адрес отправителя должен совпадать с `SMTP_USERNAME` (почтовым ящиком Zimbra). Для этого случая публичный TXT DNS **не обязателен**. Это не обход SMTP-авторизации и не подмена чужого ящика. При использовании Zimbra важны SMTP AUTH, TLS и право на адрес отправителя.

Домен `learn.company.test` должен разрешаться через внутренний DNS и открывать настоящий HTTPS-сайт платформы. **Обычный Compose по умолчанию слушает только `127.0.0.1:8080`, поэтому клиенты других компьютеров по ссылке не попадут в приложение**. Поставьте внутренний HTTPS reverse proxy с действующим для клиентов сертификатом, настройте доступ с рабочих компьютеров и добавьте домен в `DJANGO_ALLOWED_HOSTS` и `DJANGO_CSRF_TRUSTED_ORIGINS`. Не отключайте CSRF/TLS ради удобства.

Внутренние сетевые политики/маршрутизация должны исключать выход тестовой почты за разрешённые границы; `.env` не является сетевым файрволом.

## Если кнопка не запускает

Если SMTP не включён, нет активного шаблона, сотрудников, разрешённого домена получателя или ссылки, пользователь увидит понятную причину на странице сценария. Другие ошибки ищите так:

```powershell
docker compose -p $project logs --tail=150 web worker
```

При отсутствии Redis задача останется в БД в статусе `queued`. После восстановления Redis можно использовать существующую команду `dispatch_pending`, описанную в `docs/UPGRADE_V0_14_TO_V0_15.md`, без повторной отправки писем со статусом `sending`.

## Ограничения и безопасность

Отправка разрешена только аккаунту с разрешениями `scenarios.change_scenario`, `campaigns.add_campaign`, `campaigns.change_campaign`, `delivery.start_dispatch`; также требуются непустой шаблон, хотя бы один активный сотрудник, список разрешённых доменов адресатов и явное включение функции в конфигурации. Есть лимиты 250 адресатов максимум и 10 писем в минуту максимум, даже если `.env` запросит больше.

Факт `SMTP accepted` означает только принятие сервером SMTP, **не подтверждённую доставку в почтовый ящик**. Отслеживается переход по ссылке, а не достоверное чтение письма. Настоящие пароли, IP, содержимое форм и пиксели скрытого чтения не собираются.

**Проверка артефакта:** синтаксис Python, наличие файлов, структура Docker Compose, корректность шаблонных блоков и целостность ZIP. Проверить миграции, Django тесты и отправку в реальный SMTP необходимо на вашем компьютере: Docker и Django в среде сборки недоступны.
