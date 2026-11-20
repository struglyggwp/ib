# Security Awareness Platform v0.18 — сигналы открытия HTML-писем

## Новое

- Одно уникальное изображение 1×1 GIF на каждого адресата в HTML-части письма. Текстовая часть не содержит пикселя.
- Публичный endpoint `/track/open/<uuid>.gif` отвечает одинаковым изображением даже на неверный токен.
- PostgreSQL хранит только участника, тип события и серверное время. IP, User-Agent и содержимое письма не сохраняются в новой таблице.
- Повторы одного участника учитываются не чаще одного раза за 5 минут. В KPI учитываются уникальные участники.
- Письмо должно быть предварительно принято SMTP и учебная ссылка должна оставаться действительной.
- Отчёт содержит показатель «Сигнал открытия», время первого сигнала, фильтр событий и экспорт CSV.
- Nginx не пишет запросы к `/track/open/` в журнал доступа, поскольку URL содержит секретный токен.

## Ограничения

**Сигнал загрузки изображения не равен подтверждённому прочтению.** Почтовые клиенты могут блокировать внешние изображения; почтовые сканеры и прокси могут загрузить их без участия человека. Пересылка письма также не позволяет достоверно идентифицировать читателя. «Не открыт» в отчёте означает «сигнала не было».

Учитывайте применимые внутренние правила уведомления сотрудников и работы с персональными данными. Функция включена по умолчанию в v0.18, но отключается `SMTP_OPEN_TRACKING_ENABLED=0`. Это сразу прекращает регистрацию новых сигналов, включая письма, отправленные ранее. Уже существующие записи в БД не удаляются.

## Обновление с сохранением PostgreSQL

В PowerShell, находясь в папке v0.17:

```powershell
cd C:\security_awareness_platform_v0_17
docker compose ls
# Имя текущего проекта берите из docker compose ls. Например:
$project = "security_awareness_platform_v0_17"
cmd /c "docker compose -p $project exec -T db pg_dump -U awareness awareness > backup_v017.sql"
Get-Item .\backup_v017.sql | Select-Object Name,Length
```

Убедитесь, что архив резервной копии не пуст. Распакуйте `security_awareness_platform_v0_18.zip` в `C:\security_awareness_platform_v0_18`, затем:

```powershell
Copy-Item C:\security_awareness_platform_v0_17\.env C:\security_awareness_platform_v0_18\.env
cd C:\security_awareness_platform_v0_18
# Если хотите отключить сигналы, установите SMTP_OPEN_TRACKING_ENABLED=0 в .env.
docker compose -p $project --profile mailtest up -d --build

docker compose -p $project exec web python manage.py check
docker compose -p $project exec web python manage.py makemigrations --check --dry-run
docker compose -p $project exec web python manage.py test
docker compose -p $project exec web python manage.py showmigrations delivery campaigns
```

**Не применяйте `down -v`**: он удаляет том PostgreSQL. Сохраняйте имя Compose-проекта, чтобы подключиться к существующим данным. В v0.18 добавлены две миграции (`campaigns.0006`, `delivery.0002`), ранее созданные миграции не менялись. Новые токены создаются для существующих DeliveryRecord через безопасное заполнение по каждой записи.

## Как проверить с Mailpit

1. В `.env` должны оставаться рабочими `SMTP_HOST=mailpit`, `SMTP_PORT=1025`, `SMTP_ALLOWED_RECIPIENT_DOMAINS=training.test` и `SMTP_CAMPAIGN_ENABLED=1`.
2. Откройте `http://127.0.0.1:8080/campaigns/`, создайте новую кампанию с **HTML-шаблоном** и тестовым сотрудником `tester@training.test`.
3. Запустите кампанию. Откройте Mailpit `http://127.0.0.1:8025/`, найдите письмо.
4. Разрешите отображение внешних изображений в почтовом клиенте либо откройте URL `/track/open/…gif` из HTML-письма в браузере на том же компьютере.
5. Обновите страницу кампании: появится «Сигнал открытия» и время. Отдельно проверьте учебную ссылку, которая фиксируется как «Переход».
6. Если клиент не загрузил изображение автоматически, сигнал не появится. Это ожидаемое ограничение, а не обязательно ошибка.

Для Zimbra `SIMULATION_PUBLIC_BASE_URL` должен открываться из почтового клиента по HTTPS. `127.0.0.1` на другом компьютере ссылается на **тот** компьютер, не на Docker-хост.

## Тесты

```powershell
docker compose -p $project exec web python manage.py test campaigns delivery
```

Тесты проверяют регистрацию сигнала, защиту от ложных событий до SMTP, повторные загрузки, отзыв ссылки, отсутствие открытых данных в URL и отображение первого сигнала в отчёте. Не являются проверкой реального почтового клиента.
