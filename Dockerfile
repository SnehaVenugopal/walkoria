# ─── Stage 1: Build ───────────────────────────────────────────────
FROM python:3.13-slim AS builder

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies needed to build mysqlclient and python-barcode
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ─── Stage 2: Runtime ─────────────────────────────────────────────
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install only the runtime library for MySQL (not the dev headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

WORKDIR /app

# Copy project code
COPY . .

# Collect static files (uses Django's collectstatic)
# We set a dummy SECRET_KEY here just for the collectstatic step
RUN SECRET_KEY=dummy-build-key \
    DB_ENGINE=django.db.backends.sqlite3 \
    DB_NAME=:memory: \
    DB_USER='' \
    DB_PASSWORD='' \
    DB_HOST='' \
    DB_PORT='' \
    EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend \
    EMAIL_HOST=localhost \
    EMAIL_PORT=25 \
    EMAIL_USE_TLS=False \
    EMAIL_HOST_USER='' \
    EMAIL_HOST_PASSWORD='' \
    SOCIAL_AUTH_GOOGLE_OAUTH2_KEY=dummy \
    SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET=dummy \
    CLOUDINARY_NAME=dummy \
    CLOUDINARY_KEY=dummy \
    CLOUDINARY_SECRET=dummy \
    RAZORPAY_KEY_ID=dummy \
    RAZORPAY_KEY_SECRET=dummy \
    python manage.py collectstatic --noinput

EXPOSE 8000

# Start Gunicorn
CMD ["gunicorn", "walkoria.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "120"]
