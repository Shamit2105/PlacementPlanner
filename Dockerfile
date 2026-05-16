# 1. Base OS
FROM python:3.10-slim

# 2. Environment Setup
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Create working directory
WORKDIR /app

# 4. Install System-level C dependencies for PostgreSQL
RUN apt-get update \
    && apt-get install -y gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 5. Install Python libraries from the blueprint
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# 6. Copy the rest of your Django code into the container
COPY . /app/