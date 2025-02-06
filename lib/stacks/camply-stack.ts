import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import { Construct } from 'constructs';
import { CamplyLambda } from '../constructs/camply-lambda';
import { Config } from '../config';

export interface CamplyStackProps extends cdk.StackProps {
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

    // Create Lambda function
    const lambda = new CamplyLambda(this, 'Lambda', {
      cacheBucket,
      ...props.config,
    });

    // Create EventBridge rule
    const rule = new events.Rule(this, 'ScheduleRule', {
      schedule: events.Schedule.rate(cdk.Duration.minutes(props.config.scheduleRate)),
    });

    rule.addTarget(new targets.LambdaFunction(lambda.function));
  }
}
