# Dockerfile for Talawanda Enews RSS Converter
FROM python:3.11-slim

# Install system dependencies (Chromium for Selenium)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variable for chromedriver path
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Copy application code
COPY . .

# Default command
CMD ["python", "main.py"]
