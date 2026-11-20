# Обновление v0.12 → v0.13 (Windows PowerShell + Docker Desktop)

**Важно:** Сохраните БД. Не выполняйте `docker compose down -v`, `docker volume prune` или `docker system prune --volumes`.

## A. Найти Compose project name

В папке **работающей** v0.12:

```powershell
cd C:\security_awareness_platform_v0_12
docker compose ls
docker compose ps
```

Если v0.12 запускалась по прежней инструкции с `-p security_awareness_platform_v0_11`, используйте именно `security_awareness_platform_v0_11` ниже. Если имя другое, **замените его во всех командах**. Имя проекта определяет, какие volumes PostgreSQL и Redis подключаются.

## B. Резервная копия

Выполните в каталоге v0.12. Пример рассчитан на стандартные `POSTGRES_USER=awareness` и `POSTGRES_DB=awareness` (при других значениях используйте свои):

```powershell
cmd /c "docker compose -p security_awareness_platform_v0_11 exec -T db pg_dump -U awareness awareness > backup_v012.sql"
Get-Item .\backup_v012.sql | Select-Object Name,Length
```

Файл должен быть ненулевым. Храните копию **вне** папки новой версии. Рекомендуется восстановить дамп в отдельную тестовую базу прежде чем обновлять рабочую. Если `pg_dump` вернул ошибку, **не переходите** дальше.

## C. Замена исходников с сохранением volumes

1. Распакуйте архив в `C:\security_awareness_platform_v0_13`. В ZIP есть корневой каталог `security_awareness_platform_v0_13`.
2. Остановите старый стек без удаления volumes:

```powershell
cd C:\security_awareness_platform_v0_12
docker compose -p security_awareness_platform_v0_11 down
```

3. Скопируйте свой действующий `.env` (не заменяйте его демонстрационными значениями):

```powershell
Copy-Item C:\security_awareness_platform_v0_12\.env C:\security_awareness_platform_v0_13\.env
cd C:\security_awareness_platform_v0_13
```

4. Поднимите v0.13, используя **то же имя Compose project**:

```powershell
docker compose -p security_awareness_platform_v0_11 up -d --build
docker compose -p security_awareness_platform_v0_11 ps
docker compose -p security_awareness_platform_v0_11 logs --tail=100 web
```

5. Проверьте миграции и тесты:

```powershell
docker compose -p security_awareness_platform_v0_11 exec web python manage.py check
docker compose -p security_awareness_platform_v0_11 exec web python manage.py makemigrations --check --dry-run
docker compose -p security_awareness_platform_v0_11 exec web python manage.py showmigrations scenarios campaigns
docker compose -p security_awareness_platform_v0_11 exec web python manage.py test
```

Миграции выполняются entrypoint автоматически; новые `scenarios.0001_initial` и `campaigns.0003_campaign_scenario_and_participants` только добавляют таблицы/nullable-поля. Проверка `makemigrations --check --dry-run` должна сообщать «No changes detected».

6. Откройте `http://127.0.0.1:8080/scenarios/`. Доступ есть у суперпользователя, остальным нужны permissions.

## D. Права доступа

После миграций можно создать группы (пользователи в них **не** добавляются автоматически):

```powershell
docker compose -p security_awareness_platform_v0_11 exec web python manage.py setup_awareness_roles
```

Добавьте сотрудников в соответствующие группы через Django Admin → Пользователи. Группы относятся только к тем видам Django-права, на которые завязаны views. Старые экраны v0.12 пока не обеспечивают полного разграничения доступа по подразделениям; не выдавайте к ним доступ широкому кругу пользователей до реализации v0.15.

## E. Проверка пользовательского сценария

1. В «Шаблонах писем» должен быть **активный** учебный шаблон.
2. В «Сотрудниках» должен быть хотя бы один **активный** сотрудник.
3. Создайте сценарий, выберите активный шаблон и аудиторию.
4. Добавьте этапы «Учебная симуляция» и «Обратная связь и обучение».
5. Нажмите «Запустить проверку», убедитесь, что замечаний нет.
6. Нажмите «Проверить и сделать готовым».
7. Нажмите «Создать черновик кампании». Проверьте, что статус **«Черновик»**, связь на сценарий и аудитория сохранены.
8. Убедитесь, что почта никуда не отправлялась. SMTP и отправка в этом релизе отсутствуют.

## F. Диагностика

- `port is already allocated`: другой Nginx/процесс занимает 8080; остановите старый контейнер, не меняя volumes.
- `password authentication failed`: `.env` не соответствует существующему PostgreSQL volume; не удаляйте данные, восстановите прежние настройки/пароль.
- `permission denied`: пользователь не суперпользователь и не получил соответствующее разрешение `scenarios`.
- `No migrations to apply` при новых таблицах: проверьте `showmigrations` и контейнер, не подключён ли он к старому образу.
- Нет сотрудников: проверьте, что используется прежний Compose project name и не создан новый volume БД.

В случае ошибки сохраните дамп и логи. Откат на старый образ может быть возможен при обратной совместимости схемы, но безопасный путь — восстановление тестированной копии БД.
