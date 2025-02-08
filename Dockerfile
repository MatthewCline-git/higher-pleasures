FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create SQLite data directory with correct permissions
RUN mkdir -p /data/sqlite && \
    chown -R 1000:1000 /data && \
    chmod -R 777 /data/sqlite

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Add debug echo statements and ensure data directory exists
RUN echo "#!/bin/sh" > /entrypoint.sh && \
    echo "echo 'Starting application...'" >> /entrypoint.sh && \
    echo "echo 'Python version:' && python --version" >> /entrypoint.sh && \
    echo "echo 'Contents of src directory:' && ls -la src/" >> /entrypoint.sh && \
    echo "mkdir -p /data/sqlite" >> /entrypoint.sh && \
    echo "echo 'Running main.py...' && python -m src.main" >> /entrypoint.sh && \
    chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]