FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for psycopg2 and other packages
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY apps/backend/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY apps/backend .

# Expose port
EXPOSE 8000

# Start command
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
