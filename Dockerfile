FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN mkdir /data && chown 10001:10001 /data
COPY --chown=10001:10001 server.py relay.py store.py settings.py learning.py mail_delivery.py manage.py ./
COPY --chown=10001:10001 dist/ dist/

USER 10001:10001
CMD ["python", "server.py"]
