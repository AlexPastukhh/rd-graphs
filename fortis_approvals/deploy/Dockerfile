FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FORTIS_STATE_DIR=/state FORTIS_OWNER_ORIGIN=http://localhost:18990 FORTIS_PORT=18990
WORKDIR /opt/fortis
COPY fortis_approvals/requirements-owner.txt /opt/requirements-owner.txt
RUN python -m pip install --disable-pip-version-check --no-cache-dir -r /opt/requirements-owner.txt && \
    groupadd -g 10001 fortis && useradd --no-log-init -u 10001 -g 10001 -M -s /usr/sbin/nologin fortis && \
    mkdir /state && chown 10001:10001 /state && chmod 700 /state
COPY fortis_approvals /opt/fortis/fortis_approvals
USER 10001:10001
EXPOSE 18990
CMD ["python","-m","fortis_approvals.server"]
