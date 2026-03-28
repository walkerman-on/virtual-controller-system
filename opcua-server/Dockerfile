FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
	gcc \
	g++ \
	&& rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=120
COPY opcua-server/requirements.txt .
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.txt

COPY shared /app/shared
COPY opcua-server/server.py /app/

ENV PYTHONPATH=/app

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 4840

CMD ["python", "server.py"]
