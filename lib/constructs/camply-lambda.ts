import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

interface CamplyLambdaProps {
  cacheBucket: s3.IBucket;
  emailSecretArn: string;
  searchWindowDays: number
  emailSubjectLine: string;
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
        EMAIL_SECRET_ARN: props.emailSecretArn,
        SEARCH_WINDOW_DAYS: props.searchWindowDays.toString(),
        EMAIL_SUBJECT_LINE: props.emailSubjectLine,
        POWERTOOLS_SERVICE_NAME: 'camply-checker',
        POWERTOOLS_METRICS_NAMESPACE: 'CamplySiteCheck',
        LOG_LEVEL: 'INFO',
      },
    });

    props.cacheBucket.grantReadWrite(this.function);
  }
}
