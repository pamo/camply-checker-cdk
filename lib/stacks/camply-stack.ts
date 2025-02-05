import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';
import { CamplyLambda } from '../constructs/camply-lambda';
import { Config } from '../config';

interface CamplyStackProps extends cdk.StackProps {
  config: Config;
}

export class CamplyStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: CamplyStackProps) {
    super(scope, id, props);

    const cacheBucket = new s3.Bucket(this, 'CacheBucket', {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      lifecycleRules: [
        {
          expiration: cdk.Duration.days(1),
        },
      ],
    });

    // Create email secret
    const emailSecret = new secretsmanager.Secret(this, 'EmailSecret', {
      secretName: `${id}/email-config`,
      description: 'Email configuration for Camply notifications',
      generateSecretString: {
        secretStringTemplate: JSON.stringify({
          EMAIL_TO_ADDRESS: props.config.emailToAddress,
          EMAIL_USERNAME: props.config.emailUsername,
          EMAIL_SMTP_SERVER: props.config.emailSmtpServer,
          EMAIL_SMTP_PORT: props.config.emailSmtpPort,
          EMAIL_FROM_ADDRESS: props.config.emailFromAddress,
          EMAIL_PASSWORD: props.config.emailPassword,
        }),
        generateStringKey: 'EMAIL_PASSWORD',
      },
    });

    // Create Lambda function
    const lambda = new CamplyLambda(this, 'Lambda', {
      cacheBucket,
      emailSecretArn: emailSecret.secretArn,
      searchWindowDays: props.config.searchWindowDays,
      emailSubjectLine: props.config.emailSubjectLine,
    });
    emailSecret.grantRead(lambda.function);

    // Create EventBridge rule
    const rule = new events.Rule(this, 'ScheduleRule', {
      schedule: events.Schedule.rate(cdk.Duration.minutes(props.config.scheduleRate)),
    });

    rule.addTarget(new targets.LambdaFunction(lambda.function));
  }
}
