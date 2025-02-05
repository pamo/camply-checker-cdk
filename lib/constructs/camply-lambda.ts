import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

interface CamplyLambdaProps {
  cacheBucket: s3.IBucket;
  searchWindowDays: number
  emailSubjectLine: string;
  emailToAddress: string;
  emailUsername: string;
  emailPassword: string;
  emailSmtpServer: string;
  emailSmtpPort: string;
  emailFromAddress: string;
}

export class CamplyLambda extends Construct {
  public readonly function: lambda.Function;

  constructor(scope: Construct, id: string, props: CamplyLambdaProps) {
    super(scope, id);

    this.function = new lambda.Function(this, 'Function', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.lambda_handler',
      code: lambda.Code.fromAsset('lambda'),
      timeout: cdk.Duration.minutes(5),
      memorySize: 512,
      environment: {
        CACHE_BUCKET_NAME: props.cacheBucket.bucketName,
        SEARCH_WINDOW_DAYS: props.searchWindowDays.toString(),
        EMAIL_SUBJECT_LINE: props.emailSubjectLine,
        POWERTOOLS_SERVICE_NAME: 'camply-checker',
        POWERTOOLS_METRICS_NAMESPACE: 'CamplySiteCheck',
        EMAIL_TO_ADDRESS: props.emailToAddress,
        EMAIL_USERNAME: props.emailUsername,
        EMAIL_PASSWORD: props.emailPassword,
        EMAIL_SMTP_SERVER: props.emailSmtpServer,
        EMAIL_SMTP_PORT: props.emailSmtpPort,
        EMAIL_FROM_ADDRESS: props.emailFromAddress,
        LOG_LEVEL: 'INFO',
      },
    });

    props.cacheBucket.grantReadWrite(this.function);
  }
}
