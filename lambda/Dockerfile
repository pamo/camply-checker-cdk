# Use the AWS Lambda Python 3.11 base image for x86_64 architecture
FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.11

# Copy requirements and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install -r requirements.txt

# Copy function code
COPY index.py ${LAMBDA_TASK_ROOT}

CMD ["index.lambda_handler"]
