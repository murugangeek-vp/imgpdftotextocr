FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (OpenCV requires libGL, libgthread; PyMuPDF/Poppler)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libgthread-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Copy shared folder
COPY shared /app/shared

# Non-root user for security (some systems require root for OCR caches, we use appuser)
RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["python", "worker.py"]
