# Security Awareness Platform v1.0 — целевая архитектура

> Статус документа: проект архитектуры v1.0, не перечень уже внедрённых функций. Рабочий код в этом архиве имеет версию **v0.13**; новые компоненты v0.14–v1.0 отмечены как целевые. Архитектура опирается на реальные приложения v0.12: `campaigns`, `employees`, `email_templates`, `core`.

## 1. Назначение и границы

Локальная корпоративная платформа для санкционированного обучения информационной безопасности: каталог сотрудников, библиотека безопасных шаблонов, сценарии, управляемые кампании, обучение, подтверждённые события, отчётность и аудит. Запрещён сбор настоящих паролей, OTP, секретов и несанкционированная рассылка. В v0.13 нет почтового транспорта, автоматически выполняемых сценариев или реального трекинга сотрудников.

**Принципы:** модульный Django-монолит + фоновые Celery-задачи; единственная транзакционная БД PostgreSQL; Redis только для брокера/кэша; стабильные миграции; явные state transitions; неизменяемые снимки контента и аудитории для запущенных кампаний; недоверие к сигналам из внешних источников; принцип минимальных прав; защита данных сотрудников.

### Разделение ответственности

| Приложение Django | Существующее / план | Ответственность |
|---|---|---|
| `config` | есть | конфигурация, маршруты, Celery, безопасность |
| `core` | есть | интерфейс, health, админ-команды |
| `employees` | есть | сотрудники, отделы, должности, CSV; позднее группы, руководители, внешний ID |
| `email_templates` | есть | библиотека учебных сообщений, безопасный просмотр; позднее версия/снимок |
| `scenarios` | **v0.13** | сценарии, этапы, выбор аудитории, правила готовности, dry-run, аудит изменений |
| `campaigns` | есть + v0.13 | кампания, события старого типа, связь со сценарием и снимок участников |
| `accounts` | v0.15+ | доступ, роли, SSO/OIDC и MFA, организационные ограничения |
| `integrations` | v0.15+ | AD/LDAP синхронизация, авторизованный почтовый шлюз |
| `training` | v0.16+ | уроки, вопросы, тесты, прогресс, назначение обучения |
| `events` | v0.14+ | нормализованный реестр подтверждённых событий, идемпотентность |
| `analytics` | v0.14+ | агрегаты, определения метрик, фильтры, динамика |
| `reports` | v0.14+ | экспорты CSV/XLSX/PDF в очередях с разграничением доступа |
| `audit` | v0.15+ | общий неизменяемый журнал администраторских действий |
| `delivery` | v0.18+ | санкционированная отправка через корпоративный транспорт, allowlist, пауза/стоп |

Не нужно сразу переименовывать существующие приложения. Миграции сохраняются по схеме expand → backfill → switch → contract.

## 2. Топология и инфраструктура

```text
Браузер администратора (localhost / корпоративный VPN)
    |
    v
Nginx (TLS завершается на доверенном proxy в production)
    |---- /static/ --> volume static_data
    |
    +--> Django/Gunicorn web (forms, admin, API, permissions, domain services)
                   |
                   +--> PostgreSQL 16 (transactions, relations, audit)
                   |
                   +--> Redis 7 (broker, ephemeral cache)
                                   |
                                   +--> Celery worker (dry-run/aggregation/export/sync)
                                   +--> Celery beat (план v0.17)
```

Docker Compose: `db`, `redis`, `web`, `worker`, `nginx` уже работают; нельзя экспонировать PostgreSQL/Redis наружу. В будущем разделить web/worker/beat, настроить непривилегированных пользователей, restart/healthchecks, централизованные логи, TLS, резервные копии вне хоста, мониторинг ошибок. При обновлении старые named volumes должны сохраняться под тем же Compose project name. Production deployment должен фиксировать версии образов и иметь rollback-план; rollback миграций НЕ всегда возможен.

## 3. PostgreSQL: реализованная база v0.13

### `employees`
- `Department(id PK bigint, name UNIQUE, description, is_active, created_at)`.
- `Position(id PK bigint, name UNIQUE, is_active)`.
- `Employee(id PK bigint, first_name, last_name, middle_name, email UNIQUE, department_id FK PROTECT nullable, position_id FK PROTECT nullable, is_active, created_at, updated_at)`.
- Индексы на ФИО и `is_active` уже существовали в v0.12.

### `email_templates`
- `EmailTemplate(id PK bigint, name, category, tags, subject, html_body, text_body, description, status, created_by_id FK PROTECT, created_at, updated_at)`.
- Проверка HTML на этапе предпросмотра. Для v1.0 планируется отдельная неизменяемая `EmailTemplateRevision`.

### `scenarios` (новое v0.13)
- `Scenario(id PK uuid, name, description, category, difficulty, status, email_template_id FK PROTECT nullable, version, created_by_id FK PROTECT, created_at, updated_at)`.
- `Scenario.departments` M:N через Django auto-through; `Scenario.employees` M:N через Django auto-through. В аудиторию входят только активные сотрудники, объединение с устранением дублей.
- `ScenarioStep(id PK uuid, scenario_id FK CASCADE, position, kind, title, instructions, created_at)`, `UNIQUE(scenario_id, position)`. `instructions` только текст для оператора; никакого исполнения команд/HTML.
- `ScenarioRun(id PK uuid, scenario_id FK PROTECT, scenario_version, outcome, audience_count, checks JSONB, created_by_id FK PROTECT, created_at)` — только **проверочный прогон конфигурации**, не фактическое выполнение сценария.
- `ScenarioActivity(id PK bigint, scenario_id FK PROTECT, actor_id FK PROTECT, action, description, at)` — локальный журнал изменения сценария.

### `campaigns` (добавления v0.13)
- `Campaign(id PK uuid, name, description, status, starts_at, email_template_id FK SET_NULL nullable, created_by_id FK PROTECT, created_at, updated_at)` — историческая модель; **новые** `scenario_id FK PROTECT nullable`, `scenario_version nullable`. `NULL` для ранее созданных кампаний.
- `CampaignParticipant(id PK bigint, campaign_id FK CASCADE, employee_id FK PROTECT, added_at)`, `UNIQUE(campaign_id, employee_id)`. В v0.13 записи создаются при конвертации готового сценария в черновик кампании. Это снимок **состава участников**, но ещё не снимок данных письма или данных о подразделении.
- `SafeEvent` — старый учебный модуль v0.10, не следует считать достоверной персональной аналитикой до введения верификации событий.

### Кардинальности

```text
Department 1 ── N Employee N ── 1 Position
Employee M ── N Scenario N ── M Department (аудитория-правило)
EmailTemplate 1 ── N Scenario 1 ── N ScenarioStep
                            Scenario 1 ── N ScenarioRun
                            Scenario 1 ── N ScenarioActivity
                            Scenario 1 ── N Campaign (ссылка на ревизию)
Employee 1 ── N CampaignParticipant N ── 1 Campaign
EmailTemplate 1 ── N Campaign (наследованный FK)
Campaign 1 ── N SafeEvent (наследованные демонстрационные события)
```

## 4. Будущая модель PostgreSQL (проект для v1.0, сейчас НЕ реализована)

| Таблица | Ключи и важные поля | Связи/инварианты |
|---|---|---|
| `Organization` | `id UUID, name, timezone, retention_days, status` | опциональная multi-tenant схема; до её ввода одна организация |
| `EmployeeGroup` | `id, name, type(manual/dynamic)` | M:N с Employee, области видимости ролей |
| `EmployeeExternalIdentity` | `id, employee_id, provider, external_id, last_synced_at` | UNIQUE(provider, external_id), не хранить пароль AD |
| `EmailTemplateRevision` | `id, template_id, version, subject, sanitized_html, text, sha256, created_at` | UNIQUE(template_id, version), запрет изменения опубликованной версии |
| `ScenarioRevision` | `id, scenario_id, version, snapshot JSONB, sha256` | запечатывает порядок этапов, условия и шаблон |
| `CampaignApproval` | `id, campaign_id, approver_id, decision, at, comment` | обязательное согласование до реальной доставки |
| `CampaignSchedule` | `id, campaign_id UNIQUE, starts_at, ends_at, timezone, pause_reason` | хранение UTC с пользовательским timezone |
| `CampaignContentSnapshot` | `id, campaign_id UNIQUE, template_revision_id, scenario_revision_id, checksum` | создание перед согласованием, после него immutable |
| `Delivery` | `id, campaign_participant_id, provider_message_id, state, attempts, last_error` | UNIQUE(campaign_participant_id) и idempotency key |
| `VerifiedEvent` | `id UUID, campaign_id, participant_id?, kind, source, occurred_at, received_at, credibility, idempotency_key` | UNIQUE(source,idempotency_key); только подтверждённые события |
| `TrainingModule` | `id, title, version, content, status` | sanitization и публикация версий |
| `TrainingAssignment` | `id, employee_id, campaign_id?, training_module_id, deadline, status` | не создавать дубли на одно назначение |
| `TrainingAttempt` | `id, assignment_id, started_at, finished_at, score, passed` | отдельные попытки/ревизии вопросов |
| `ReportJob` | `id, requester_id, scope, filters JSONB, status, file_ref, expires_at` | проверять доступ и при запросе, и при скачивании |
| `AuditRecord` | `id UUID, actor_id, action, object_type, object_id, before/after metadata JSONB, at, trace_id` | без секретов; ограничение экспорта и retention |
| `RoleScope` | `id, user_id, permission_role, department_id?` | объектно-уровневые ограничения для руководителей |
| `IntegrationRun` | `id, provider, started_at, finished_at, outcome, counts` | идемпотентная синхронизация, журнал ошибок |

Выпуск multi-tenant (`Organization`) откладывать до реальной потребности: добавление `organization_id` в каждую таблицу — крупная миграция, её нельзя сделать незаметно.

## 5. Роли и разграничение прав

| Действие | Администратор | Специалист ИБ | Руководитель | Аудитор | Сотрудник |
|---|---:|---:|---:|---:|---:|
| Инфраструктура, роли, секреты | да | нет | нет | нет | нет |
| Создание шаблонов и сценариев | да | да | нет | нет | нет |
| Согласование кампании | по правилам | отдельный согласующий | нет | нет | нет |
| Запуск/остановка согласованной кампании | да | по роли | нет | нет | нет |
| Просмотр индивидуальных результатов | ограниченно | по назначению | только согласованный scope | согласно мандату | только свои |
| Агрегированная аналитика | да | да | своего подразделения | по мандату | нет |
| Прохождение обучения | нет | нет | как сотрудник | как сотрудник | да |
| История аудита | да | ограниченно | нет | да | нет |

v0.13: в новом приложении применены стандартные Django model permissions (`view`, `add`, `change`). Команда `setup_awareness_roles` создаёт две группы, **но не добавляет пользователей**. Старые view-функции v0.12 пока используют `login_required`, а не полную RBAC; это открытый технический долг, который нужно закрыть до production v1.0. Доступ к `/admin` требует `is_staff`. Важный инвариант: нельзя наделять руководителя `view_employee` глобально, если нужен только один отдел. Для v1.0 нужен policy layer на каждом queryset и каждой операции.

## 6. Доменная модель и жизненные циклы

**Scenario:** `draft -> ready -> archived`, `archived -> draft`. После изменения параметров/этапов любой готовый сценарий становится черновиком и повышает ревизию. `ready` разрешён только с активным шаблоном, активной аудиторией, этапами `simulate` и `teach`. Проверка выполняется на сервере. Готовность пересматривается при создании кампании, т.к. состояние аудитории могло измениться.

**Campaign v0.13:** из готового сценария создаётся **только** `draft`. При этом сохраняются `scenario_id`, `scenario_version`, список `CampaignParticipant`. Нет автоматической смены статуса и нет доставки. Старый CRUD кампаний сохранён, включая наследованные статусы; его следует перевести на отдельный сервис переходов в v0.17.

**Campaign v1.0 (план):** `draft -> review -> approved -> scheduled -> running -> completed -> archived`, ветви `cancelled`, `paused`, `failed`. Смену состояния выполняет только транзакционный сервис `CampaignTransitionService` с permission check, журналом причин, optimistic lock, подтверждением согласования и идемпотентностью. Администратор не может вручную ставить `running` через ModelForm. Отмена блокирует последующие задания доставки.

**Email delivery (только после v0.18):** проверка корпоративного домена получателей, consent/approval, лимит отправки, stop switch, correlation IDs, безопасная ссылка без секретов, повторные попытки только с идемпотентным ключом. Сырые токены доступа не логируются; адреса и домены разрешены только владельцем системы.

## 7. Бизнес-процессы

1. **Справочник:** кадровый администратор импортирует сотрудников, сверяет ошибки, деактивирует ушедших. В v1.0 происхождение данных фиксируется в `IntegrationRun`.
2. **Подготовка:** специалист ИБ создаёт/публикует шаблон; собирает сценарий, выбирает аудиторию и этапы.
3. **Валидация:** `dry_run` анализирует наличие необходимых элементов, количество действующих участников, наличие активного шаблона. Никакой фактической симуляции или отправки.
4. **Кампания:** из готового сценария создаётся черновик со снимком аудитории и ссылкой на ревизию. Для v1.0 дополнительно фиксируются версии контента, согласование и расписание.
5. **Исполнение (план):** ограниченный delivery worker, контроль статуса, аварийная остановка, события с доказуемым источником.
6. **Обучение (план):** по результатам событий назначаются уроки, сотрудники проходят тестирование.
7. **Аналитика (план):** агрегаты из верифицированных данных, не из сырых HTTP hits. Раздельные метрики «письмо принято транспортом», «письмо доставлено», «подтверждённый переход», «сообщил о подозрении», «прошёл обучение».
8. **Отчёты и retention (план):** export jobs со scope, CSV/XLSX/PDF, TTL, удаление/анонимизация данных согласно политике организации.

## 8. API и сервисный слой

Для v1.0: versioned API `/api/v1/` с DRF; pagination, filters, permission classes, per-object scopes; запросы на смену статуса POST с CSRF/session (внутренний UI) или узко scoped API-токены с ротацией. Рекомендуемые ресурсы:

```text
GET/POST /api/v1/scenarios/
GET/PATCH /api/v1/scenarios/{id}/
POST /api/v1/scenarios/{id}/validate/
POST /api/v1/scenarios/{id}/create-campaign/
GET/POST /api/v1/campaigns/
POST /api/v1/campaigns/{id}/approve/
POST /api/v1/campaigns/{id}/pause/
POST /api/v1/campaigns/{id}/cancel/
GET /api/v1/reports/?period=...
```

v0.13 реализует **HTML web views** `/scenarios/` с POST+CSRF, а не эти API. Бизнес-правила вынесены в `scenarios/services.py`, поэтому API можно будет добавить без дублирования логики.

## 9. События, очередь, идемпотентность

- PostgreSQL — источник истины, Redis не используется как долговременное хранилище кампаний.
- Celery task принимает только ID, перечитывает объект из БД и повторно проверяет состояние/права/политику; уникальный ключ исключает повторную отправку.
- Для production рекомендуется transactional outbox (`OutboxEvent`) для согласованности транзакции PostgreSQL и постановки фоновой задачи.
- События внешнего провайдера должны иметь подписанный webhook или подтверждаемую корреляцию, `idempotency_key`, ограниченный TTL и отметку достоверности. Обычный HTTP GET/открытие пикселя не равен действию человека.
- Соблюдать минимизацию персональных данных: не хранить пароль, OTP, полное содержимое форм, лишние IP и user-agent; продумать retention и юридическое основание обработки.

## 10. Устойчивость и эксплуатация

- Перед обновлением: `pg_dump` + проверить, что файл ненулевой и тестово восстанавливается в отдельной БД.
- Изменение схемы PostgreSQL только через проверенные Django migrations; не использовать `makemigrations` на production без ревью.
- Rollback приложения поддерживает совместимость схемы не всегда: делать backup до upgrade и тестировать restore.
- `check --deploy` для production-настроек; для localhost могут требоваться отдельные настройки TLS. Не публиковать Docker socket, PostgreSQL или Redis.
- Целевые, согласуемые SLO: доступность 99.5% в рабочее время, RPO <=24 ч при ночных backups, RTO <=4 ч при проверенном restore (цели, а не обещанные показатели).
- Тесты: Django models/services/forms/views, permissions, multi-user concurrency, миграции на копии v0.12 БД, XSS, экспорт, backup-restore, healthchecks, Redis outage, idempotency.

## 11. Этапы релизов

| Релиз | Фокус | Проверяемый критерий завершения |
|---|---|---|
| v0.13 — этот архив | сценарии, этапы, выбор аудитории, dry-run, история, снимок участников | на базе v0.12 применяются миграции; можно создать готовый сценарий и черновик кампании; письма не уходят |
| v0.14 | нормализованные события, аналитика, CSV/PDF/XLSX отчёты | показатели подтверждаются набором fixture-событий; доступ к отчётам ограничен |
| v0.15 | роли, scope, SSO/OIDC/AD sync, общий audit | проверены запреты и разграничение по подразделениям |
| v0.16 | обучение: уроки, вопросы, тесты, назначения | завершение обучения корректно отражается в статистике |
| v0.17 | планировщик, переходы статусов, ревизии и согласование | нет обхода согласования, двойного исполнения или потери расписания |
| v0.18 | разрешённая корпоративная доставка (опционально) | allowlist/лимиты/stop switch/идемпотентность проверены; нет сбора секретов |
| v0.19 | нагрузка, backup/restore, security hardening, observability | регрессионные + интеграционные тесты проходят в стенде |
| v1.0 | релиз, документация, мониторинг, политика данных | приемочные E2E-сценарии и эксплуатационный runbook подписаны |

**Решение:** сначала принимать v0.13 с сохранением v0.12 данных, затем развивать модули по этапам. Архитектура целевая, а не выдуманное «v1.0 уже готово».
