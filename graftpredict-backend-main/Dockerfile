# Multi-stage Dockerfile for production
FROM python:3.11-slim as builder
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim
RUN groupadd -r app && useradd -r -g app app
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY . /app
RUN chown -R app:app /app
USER app
EXPOSE 8000
ENV GUNICORN_CMD_ARGS="-w ${GUNICORN_WORKERS:-2} -b 0.0.0.0:8000"
CMD ["/usr/local/bin/gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "wsgi:app"]
