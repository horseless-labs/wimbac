FROM python:3.13-slim

# Prevent Python from writing .pyc files and buffer logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
# gcc is useful if any Python package needs compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*


# Install Python dependencies first for better Docker layer caching
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Flask/Gunicorn will listen inside Docker.
EXPOSE 8000

# Default prduction-ish command
CMD ["gunicorn", "--workers", "2", "--threads", "2", "--timeout", "60", "--bind", "0.0.0.0:8000", "app:app"]