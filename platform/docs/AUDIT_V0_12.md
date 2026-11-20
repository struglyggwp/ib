# v0.12 implementation and validation notes

## Implemented

- `email_templates` app with model, admin, forms, authenticated CRUD views and URL routes.
- Category, comma-separated tags, status, subject, HTML body, text body and internal description.
- Demo variable substitution in preview; unknown placeholders remain literal.
- HTML preview is sanitized with Bleach allowlists. The preview does not execute author-supplied scripts or event handlers; anchor destinations and remote images are not loaded.
- Optional `Campaign.email_template` relation using `SET_NULL`; deleting a template does not delete its campaign.
- Dashboard count and navigation entry for templates.
- Celery worker runs as UID/GID 10001.
- Corrective migration for pre-existing verbose-name differences in Campaign/SafeEvent fields, plus the campaign-template relation.
- Employee model index names aligned with the checked-in v0.11 initial migration to avoid needless remove/recreate migration churn.

## Explicitly not implemented

- SMTP configuration, sending, tracking pixels, credential capture, password/OTP collection or automated campaign launch.
- Role-based authorization beyond the existing login requirement.
- Rich WYSIWYG editor. HTML is edited as source and previewed after sanitization.

## Validation performed in the build workspace

- Python source files passed `python -m compileall`.
- Migration dependencies and model/migration field definitions were reviewed manually.
- Docker, Django runtime and PostgreSQL integration tests could not be executed in the build workspace because Docker/Django are not installed and package downloads are unavailable there.

## Required validation on the deployment host

After building and starting the stack, run:

```powershell
docker compose -p security_awareness_platform_v0_11 exec web python manage.py check
docker compose -p security_awareness_platform_v0_11 exec web python manage.py makemigrations --check --dry-run
docker compose -p security_awareness_platform_v0_11 exec web python manage.py test
```

The `makemigrations --check --dry-run` command should report no model changes. If it reports any, stop before using the new release and retain the output for diagnosis.
