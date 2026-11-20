# Эксплуатация

## Проверка
`docker compose ps`
`docker compose logs --tail=100 web`
`docker compose exec web python manage.py check`
`docker compose exec web python manage.py showmigrations`

## Резервная копия PostgreSQL
`docker compose exec -T db pg_dump -U awareness awareness > awareness_backup.sql`

## Восстановление
Создать пустую БД и выполнить:
`Get-Content .\\awareness_backup.sql | docker compose exec -T db psql -U awareness awareness`

## Обновление
Сделать backup, заменить код, затем:
`docker compose up -d --build`
`docker compose exec web python manage.py migrate`

Не удаляйте volume `postgres_data` при обычном обновлении.
