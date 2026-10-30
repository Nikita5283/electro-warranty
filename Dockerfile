FROM python:3.12-slim

WORKDIR /app

# Установка системных утилит (curl для healthcheck контейнеров)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кодовой базы
COPY . /app

# Отключение буферизации для мгновенного вывода логов
ENV PYTHONUNBUFFERED=1

EXPOSE 8000 8001 8003 8004 9000
