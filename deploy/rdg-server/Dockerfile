FROM node:24-bookworm-slim AS node
FROM python:3.11-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 libatomic1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 rdg && useradd --uid 10001 --gid rdg --no-create-home rdg \
    && mkdir /data && chown rdg:rdg /data
WORKDIR /app
COPY runtime/tools/requirements-server.txt /app/tools/requirements-server.txt
RUN pip install --no-cache-dir -r tools/requirements-server.txt
COPY runtime/ /app/
RUN node --version && python3 -m gunicorn --version
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RDG_DATA_DIR=/data
USER 10001:10001
EXPOSE 8080
CMD ["python3", "-m", "gunicorn", "--chdir", "/app/tools", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "1", "--timeout", "60", "--graceful-timeout", "30", "--worker-tmp-dir", "/tmp", "--access-logfile", "/dev/null", "--log-level", "warning", "rdg_server_entry:application"]
