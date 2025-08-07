# Use the official camply Docker image with explicit AMD64 platform
FROM --platform=linux/amd64 juftin/camply:latest

# Install AWS Lambda Runtime Interface Client and fix numpy/pandas compatibility
COPY requirements.txt /tmp/
RUN pip install awslambdaric && \
    pip install --no-deps boto3 botocore jmespath python-dateutil s3transfer urllib3 && \
    pip uninstall -y numpy pandas && \
    pip install numpy==1.24.3 pandas==1.5.3 --no-cache-dir

# Set Lambda environment
ENV LAMBDA_TASK_ROOT=/var/task
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy function code and all required modules
COPY index.py ${LAMBDA_TASK_ROOT}/
COPY camply_filesystem_patch.py ${LAMBDA_TASK_ROOT}/
COPY s3_result_store.py ${LAMBDA_TASK_ROOT}/
COPY result_comparator.py ${LAMBDA_TASK_ROOT}/
COPY multi_email_notifier.py ${LAMBDA_TASK_ROOT}/
COPY email_config_parser.py ${LAMBDA_TASK_ROOT}/
COPY metrics_publisher.py ${LAMBDA_TASK_ROOT}/

# Set the Lambda runtime
ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
CMD ["index.lambda_handler"]
