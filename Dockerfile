# Используем официальный образ Python
FROM python:3.10-slim

# Установка Poetry
RUN pip install poetry

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    python3-apt \
    pkg-config \
    libcairo2-dev \
    libgirepository1.0-dev \
    build-essential \
    python3-dev \
    libyaml-dev \
    libpq-dev \
    libsystemd-dev \
    && apt-get clean

# Создаем директорию для приложения
WORKDIR /app

# Копируем pyproject.toml и poetry.lock в контейнер
COPY pyproject.toml poetry.lock* /app/

# Устанавливаем зависимости через Poetry
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

# Копируем остальной код в контейнер
COPY . /app/

# Указываем команду запуска бота
CMD ["poetry", "run", "python", "bot.py"]
