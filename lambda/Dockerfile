# Use Python 3.11 slim image to avoid numpy conflicts
FROM --platform=linux/amd64 python:3.11-slim

# Set working directory
WORKDIR /var/task

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install AWS Lambda Runtime Interface Client
RUN pip install awslambdaric

# Copy function code
COPY index.py .

# Set the Lambda runtime
ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
CMD ["index.lambda_handler"]
