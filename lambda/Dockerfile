# Use Python 3.11 slim image to avoid numpy conflicts
FROM python:3.11-slim

# Set working directory
WORKDIR /var/task

# Version marker for x86_64 architecture - Force rebuild 2026-02-17-15:11
RUN echo "x86_64 version 2.1.0" > /tmp/version.txt

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY lambda/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install AWS Lambda Runtime Interface Client
RUN pip install awslambdaric

# Copy function code and config
COPY lambda/ .
COPY config/ ./config/

# Set the Lambda runtime
ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
CMD ["index.lambda_handler"]
