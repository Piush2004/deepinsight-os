FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies for psycopg2 and standard builds
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose the API port
EXPOSE 8000

# Create a non-root user for security
RUN adduser --disabled-password --gecos '' appuser
USER appuser

# Health check logic runs via Docker Compose or k8s
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
