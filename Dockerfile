# 1. Base OS
FROM python:3.10-slim

# 2. Environment Setup
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# 3. Create working directory
WORKDIR /app

# 4. Install System-level dependencies
RUN apt-get update \
    && apt-get install -y gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy requirements first
COPY requirements.txt /app/

# 6. Upgrade pip
RUN pip install --upgrade pip

# 7. Install CPU-only PyTorch FIRST
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

# 8. Install remaining requirements
RUN pip install -r requirements.txt

# 9. Copy project files
COPY . /app/
