# Переход Security Awareness Platform v0.14-preview → v0.15

## Перед началом

v0.15 **сохраняет** приложения `campaigns`, `employees`, `email_templates`, `scenarios`, PostgreSQL и существующие данные. Новое приложение `delivery` добавляет только собственные таблицы. Его миграция — `delivery/0001_initial.py`.

**Важно:** это кодовая сборка, не прошедшая интеграционный запуск Docker в среде подготовки. Перед применением на рабочей БД сделайте backup, проверьте миграции и тесты. Сначала испытайте на копии базы.

### В PowerShell на Windows

В выводе пользователя имя старого проекта было `security_awareness_platform_v0_14_preview`. Если ваше имя другое, замените его в командах ниже.

```powershell
$old = 'C:\security_awareness_platform_v0_14_preview'
$new = 'C:\security_awareness_platform_v0_15'
$project = 'security_awareness_platform_v0_14_preview'
cd $old
docker compose -p $project ps
cmd /c "docker compose -p $project exec -T db pg_dump -U awareness awareness > backup_v014_before_v015.sql"
Get-Item .\backup_v014_before_v015.sql | Select-Object Name,Length
```

Если файл backup пустой или команда завершилась ошибкой, **остановитесь**. Сделайте копию этого SQL вне рабочей папки.

Распакуйте новый ZIP в `C:\security_awareness_platform_v0_15` (в этой папке должен лежать `docker-compose.yml`). Затем:

```powershell
Copy-Item "$old\.env" "$new\.env"
cd $old
docker compose -p $project down
cd $new
notepad .env
```

Добавьте новые настройки, не меняя сохранённые пароли PostgreSQL и Django:

```env
SMTP_CAMPAIGN_ENABLED=0
SMTP_ALLOWED_RECIPIENT_DOMAINS=
SMTP_MAX_PER_CAMPAIGN=100
SMTP_MAX_PER_MINUTE=10
SIMULATION_PUBLIC_BASE_URL=
```

**Не включайте `SMTP_CAMPAIGN_ENABLED=1` сразу, если используете живую Zimbra.** Сначала убедитесь в правильности разрешённых доменов и проверок.

```powershell
docker compose -p $project --profile mailtest up -d --build
docker compose -p $project ps
docker compose -p $project exec web python manage.py check
docker compose -p $project exec web python manage.py makemigrations --check --dry-run
docker compose -p $project exec web python manage.py showmigrations delivery
docker compose -p $project exec web python manage.py test
```

Первая миграция `delivery` должна помечаться `[X]`. В диагностике `makemigrations` ожидается `No changes detected`. При любых ошибках **не выполняйте** `makemigrations` без проверки модели и миграции. Контейнер web автоматически запускает `migrate` при старте.

**Никогда не запускайте `docker compose down -v`**, пока нужны данные старой версии. Чтобы остановить все сервисы и сохранить volumes: `docker compose -p $project down`.

## Проверка на Mailpit без внешней почты

В `.env` установите:

```env
SMTP_HOST=mailpit
SMTP_PORT=1025
SMTP_USE_STARTTLS=0
SMTP_USE_SSL=0
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=training@training.test
SMTP_TEST_RECIPIENTS=tester@training.test
SMTP_CAMPAIGN_ENABLED=1
SMTP_ALLOWED_RECIPIENT_DOMAINS=training.test
SMTP_MAX_PER_CAMPAIGN=25
SMTP_MAX_PER_MINUTE=5
```

Пересоздайте web и worker, не меняя базу:

```powershell
docker compose -p $project --profile mailtest up -d --force-recreate web worker mailpit
```

1. Откройте `http://127.0.0.1:8080/delivery/domains/`. Добавьте `training.test` и нажмите «Проверить»: специальный режим `.test` допускается **только при SMTP_HOST=mailpit**, без DNS.
2. В каталоге сотрудников создайте тестового сотрудника `tester@training.test`.
3. Создайте и активируйте учебный шаблон письма. В сценариях выберите этого сотрудника, шаблон, обязательные этапы, выполните проверку и создайте черновик кампании.
4. В кампании поменяйте статус на «Согласована» и откройте ссылку «Учебная рассылка» на странице отчёта.
5. Прочитайте список проверок и подтвердите разрешение организации, затем нажмите запуск. Письмо появится в `http://127.0.0.1:8025/`.
6. В Mailpit нажмите на персональную ссылку. Учебная страница локально откроется, в отчёте кампании появится время перехода. Нажмите «Я ознакомился», чтобы зарегистрировать завершение.
7. CSV отчёт доступен на странице кампании. `SMTP принято` означает только успешную передачу SMTP-серверу, **не подтверждённую доставку**.

Тестовые письма локально не отправляются наружу. Ссылка `127.0.0.1` из таких писем открывается на том же компьютере. Это не подходит для реальных получателей в сети.

## Подключение к Zimbra

Zimbra — отдельный уже настроенный сервер; ZIP **не устанавливает Zimbra**. Потребуются SMTP Submission, тестовая учётная запись отправителя, разрешённые корпоративные адресаты и собственный учебный домен с рабочим HTTPS.

Пример конфигурации (замените все домены и секреты своими):

```env
SMTP_HOST=mail.lab.company.example
SMTP_PORT=587
SMTP_USE_STARTTLS=1
SMTP_USE_SSL=0
SMTP_USERNAME=training@training.company.example
SMTP_PASSWORD=YOUR_SECRET
SMTP_FROM_EMAIL=training@training.company.example
SMTP_TEST_RECIPIENTS=tester@company.example
SMTP_CAMPAIGN_ENABLED=0
SMTP_ALLOWED_RECIPIENT_DOMAINS=company.example
SIMULATION_PUBLIC_BASE_URL=https://training.company.example
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,training.company.example
DJANGO_CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8080,https://training.company.example
```

`training.company.example` должен быть **под контролем организации**, разрешён для использования и настроен в Zimbra как почтовый домен/отправитель. В разделе `/delivery/domains/` добавьте его, опубликуйте DNS TXT `_awareness-verify.training.company.example` со значением, которое покажет платформа, затем подтвердите запись в интерфейсе.

Настройте публичный HTTPS reverse proxy и маршрутизацию к платформе. Текущий Nginx Docker слушает только `127.0.0.1:8080`: он **не доступен удалённым сотрудникам** без дополнительной сетевой конфигурации. Не подключайте внешнюю почту, пока HTTPS-страница недоступна и тестовые письма не проходят штатную проверку SMTP. SPF/DKIM/DMARC должны оставаться активны; обход почтовой защиты не предусмотрен.

Включать `SMTP_CAMPAIGN_ENABLED=1` следует только после успешной одиночной проверки через `/campaigns/mail/`, согласования адресатов и настройки доменов. Разрешены только адреса с **точным** совпадением домена из `SMTP_ALLOWED_RECIPIENT_DOMAINS`.

## Мониторинг, ограничения и восстановление очереди

```powershell
docker compose -p $project logs --tail=120 worker
docker compose -p $project logs --tail=120 web
```

- Один SMTP-запуск на кампанию. Максимум 250 участников, ограничение по умолчанию 100. Максимум 10 передач в минуту глобально, лимит настраивается только вниз.
- Система сохраняет снимок шаблона и адресов участников в момент запуска.
- Ошибки SMTP и двусмысленные сетевые таймауты **не повторяются автоматически**: повтор мог бы отправить дубль. Состояние `sending` после сбоя требует ручной проверки.
- Если Redis был недоступен в момент постановки задания, запись остаётся `queued`. После восстановления Redis выполните: `docker compose -p $project exec web python manage.py dispatch_pending`.
- Кнопка «Экстренная остановка» останавливает очередь, отменяет кампанию и блокирует новые переходы. Принятые ранее SMTP письма нельзя отозвать.
- Событие перехода указывает владельца учебной ссылки, но не доказывает личность посетителя. Почтовые шлюзы могут открывать ссылки автоматически. Пикселей скрытого отслеживания и форм сбора паролей нет.
- URL c личными токенами не выводятся в access-логи Nginx и Gunicorn.

## Если старый контейнер уже удалён

Выполните `docker volume ls`. Если остался `security_awareness_platform_v0_14_preview_postgres_data`, сохраняйте прежнее имя проекта через `-p security_awareness_platform_v0_14_preview`. Если volume и backup отсутствуют, это будет новая пустая база.
