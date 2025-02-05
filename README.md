# Camply Checker
This repository contains the AWS CDK infrastructure for the Camply campsite availability checker. It includes a Lambda function that periodically checks for campsite availability and sends email notifications.

## Prerequisites
* Node.js (>= 18.0.0)
* AWS CLI configured with appropriate credentials
* AWS CDK installed globally (`npm install -g aws-cdk`)

## Setup
### Install Dependencies: Install the necessary dependencies by running:
```
npm install
```

### Bootstrap the CDK Environment: Bootstrap your AWS environment if you haven't already:

```
npm run bootstrap
```

### Build the Project: Compile the TypeScript code to JavaScript:
```
npm run build
```

Deployment
Deploy to Development Environment
To deploy the stacks to the development environment, run:
```
npm run deploy:dev
```

Deploy to Production Environment
To deploy the stacks to the production environment, run:
```
npm run deploy:prod
```

## Configuration
The configuration for the project is managed using environment variables. Create a .env file in the root directory with the following content:

```
EMAIL_TO_ADDRESS="your-email@example.com"
EMAIL_USERNAME="your-email@example.com"
EMAIL_PASSWORD="your-email-password"
EMAIL_SMTP_SERVER="smtp.your-email-provider.com"
EMAIL_SMTP_PORT="465"
EMAIL_FROM_ADDRESS="camply@your-domain.com"
EMAIL_SUBJECT_LINE="Camply Notification"
```

## GitHub Actions
The repository includes a GitHub Actions workflow for deploying the Lambda function. The workflow is defined in deploy.yml.

## Testing

To run the tests, use:
```
npm test
```

## CDK Stacks
### CamplyStack
The CamplyStack defined in `camply-stack.ts` includes:

* An S3 bucket for caching
* A Lambda function for checking campsite availability
* An EventBridge rule to trigger the Lambda function periodically

### GithubActionsStack
The GithubActionsStack defined in `github-actions-stack.ts` includes:

* An IAM role for GitHub Actions with permissions to deploy the CDK stacks
