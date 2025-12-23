import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as snsSubscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as cloudwatchActions from 'aws-cdk-lib/aws-cloudwatch-actions';
import * as iam from 'aws-cdk-lib/aws-iam';

import { Construct } from 'constructs';

interface CamplyLambdaProps {
  cacheBucket: s3.IBucket;
  searchWindowDays: number;
  emailSubjectLine: string;
  emailToAddress: string;
  emailUsername: string;
  emailPassword: string;
  emailSmtpServer: string;
  emailSmtpPort: string;
  emailFromAddress: string;
  alertEmailAddress: string;
}

export class CamplyLambda extends Construct {
  public readonly function: lambda.Function;

  constructor(scope: Construct, id: string, props: CamplyLambdaProps) {
    super(scope, id);

    // Skip bundling during tests to avoid Docker dependency issues
    const shouldBundle = process.env.NODE_ENV !== 'test' && !process.env.CDK_DISABLE_BUNDLING;

    if (shouldBundle) {
      this.function = new lambda.Function(this, 'Function', {
        runtime: lambda.Runtime.FROM_IMAGE,
        code: lambda.Code.fromAssetImage('lambda', {
          cmd: ['index.lambda_handler'],
          buildArgs: {
            CACHE_BUST: Date.now().toString(),
          },
        }),
        handler: lambda.Handler.FROM_IMAGE,
        architecture: lambda.Architecture.ARM_64,
        timeout: cdk.Duration.minutes(3),
        memorySize: 256,
        description: `Camply checker function - deployed ${new Date().toISOString()}`,
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
          DEPLOYMENT_TIMESTAMP: Date.now().toString(), // Force update
        },
      });
    } else {
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
          DEPLOYMENT_TIMESTAMP: Date.now().toString(), // Force update
        },
      });
    }

    props.cacheBucket.grantReadWrite(this.function);

    // Grant permissions to publish CloudWatch metrics
    this.function.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['cloudwatch:PutMetricData'],
        resources: ['*'],
        conditions: {
          StringEquals: {
            'cloudwatch:namespace': 'CamplySiteCheck/Notifications',
          },
        },
      })
    );

    // Create SNS topic for alerts - use the same email as emailToAddress
    const alertTopic = new sns.Topic(this, 'AlertTopic', {
      displayName: 'Camply Lambda Alerts',
    });

    // Use dedicated alert email address for CloudWatch SNS notifications
    alertTopic.addSubscription(new snsSubscriptions.EmailSubscription(props.alertEmailAddress));

    // Error rate alarm
    const errorAlarm = new cloudwatch.Alarm(this, 'ErrorAlarm', {
      metric: this.function.metricErrors({
        period: cdk.Duration.minutes(5),
      }),
      threshold: 1,
      evaluationPeriods: 1,
      alarmDescription: 'Camply Lambda function errors',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    errorAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alertTopic));

    // Duration alarm (if function takes too long)
    const durationAlarm = new cloudwatch.Alarm(this, 'DurationAlarm', {
      metric: this.function.metricDuration({
        period: cdk.Duration.minutes(5),
      }),
      threshold: 240000, // 4 minutes (240 seconds in milliseconds)
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      alarmDescription: 'Camply Lambda function taking too long',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    durationAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alertTopic));

    // Throttle alarm
    const throttleAlarm = new cloudwatch.Alarm(this, 'ThrottleAlarm', {
      metric: this.function.metricThrottles({
        period: cdk.Duration.minutes(5),
      }),
      threshold: 1,
      evaluationPeriods: 1,
      alarmDescription: 'Camply Lambda function throttled',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    throttleAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alertTopic));

    // Email delivery failure alarm
    const emailFailureAlarm = new cloudwatch.Alarm(this, 'EmailDeliveryFailureAlarm', {
      metric: new cloudwatch.Metric({
        namespace: 'CamplySiteCheck/Notifications',
        metricName: 'EmailDeliveryFailure',
        statistic: 'Sum',
        period: cdk.Duration.minutes(15),
      }),
      threshold: 1,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      alarmDescription: 'Email delivery failures detected',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    emailFailureAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alertTopic));

    // Email delivery success rate alarm (trigger if success rate drops below 80%)
    const emailSuccessRateAlarm = new cloudwatch.Alarm(this, 'EmailSuccessRateAlarm', {
      metric: new cloudwatch.Metric({
        namespace: 'CamplySiteCheck/Notifications',
        metricName: 'EmailDeliverySuccessRate',
        statistic: 'Average',
        period: cdk.Duration.minutes(15),
      }),
      threshold: 80,
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
      alarmDescription: 'Email delivery success rate below 80%',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    emailSuccessRateAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alertTopic));

    // Secret retrieval failure alarm
    const secretFailureAlarm = new cloudwatch.Alarm(this, 'SecretRetrievalFailureAlarm', {
      metric: new cloudwatch.Metric({
        namespace: 'CamplySiteCheck/Notifications',
        metricName: 'SecretRetrievalFailure',
        statistic: 'Sum',
        period: cdk.Duration.minutes(15),
      }),
      threshold: 1,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      alarmDescription: 'AWS Secrets Manager retrieval failures detected',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    secretFailureAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alertTopic));

    // S3 operation failure alarm
    const s3FailureAlarm = new cloudwatch.Alarm(this, 'S3OperationFailureAlarm', {
      metric: new cloudwatch.Metric({
        namespace: 'CamplySiteCheck/Notifications',
        metricName: 'S3OperationFailure',
        statistic: 'Sum',
        period: cdk.Duration.minutes(15),
      }),
      threshold: 3, // Allow some failures but alert if too many
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      alarmDescription: 'Multiple S3 operation failures detected',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    s3FailureAlarm.addAlarmAction(new cloudwatchActions.SnsAction(alertTopic));
  }
}
