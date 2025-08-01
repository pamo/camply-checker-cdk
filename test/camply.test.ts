import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { CamplyStack, CamplyStackProps } from '../lib/stacks/camply-stack';
import { Config } from '../lib/config';

describe('CamplyStack', () => {
  let app: cdk.App;
  let stack: CamplyStack;
  let template: Template;

  beforeAll(() => {
    app = new cdk.App();
    const env = { account: '123456789012', region: 'us-west-2' };
    const config = new Config('dev');
    const props: CamplyStackProps = { env, config };
    stack = new CamplyStack(app, 'TestStack', props);
    template = Template.fromStack(stack);
  });

  test('S3 Cache Bucket Created', () => {
    template.hasResourceProperties('AWS::S3::Bucket', {
      LifecycleConfiguration: {
        Rules: [
          {
            ExpirationInDays: 1,
            Status: 'Enabled',
          },
        ],
      },
    });
  });

  test('Lambda Function Created with Correct Properties', () => {
    template.hasResourceProperties('AWS::Lambda::Function', {
      Handler: 'index.lambda_handler',
      Runtime: 'python3.11',
      Timeout: 300,
      MemorySize: 512,
      Environment: {
        Variables: {
          POWERTOOLS_SERVICE_NAME: 'camply-checker',
          POWERTOOLS_METRICS_NAMESPACE: 'CamplySiteCheck',
          LOG_LEVEL: 'INFO',
          SEARCH_WINDOW_DAYS: Match.anyValue(),
          CACHE_BUCKET_NAME: Match.anyValue(),
          EMAIL_TO_ADDRESS: Match.anyValue(),
          EMAIL_USERNAME: Match.anyValue(),
          EMAIL_PASSWORD: Match.anyValue(),
          EMAIL_SMTP_SERVER: Match.anyValue(),
          EMAIL_SMTP_PORT: Match.anyValue(),
          EMAIL_FROM_ADDRESS: Match.anyValue(),
        },
      },
    });
  });

  test('Lambda Function uses bundled dependencies', () => {
    template.hasResourceProperties('AWS::Lambda::Function', {
      Code: {
        S3Bucket: Match.anyValue(),
        S3Key: Match.anyValue(),
      },
    });
  });

  test('S3 Bucket Policy Created', () => {
    template.hasResourceProperties('AWS::S3::BucketPolicy', {
      PolicyDocument: {
        Statement: Match.arrayWith([
          Match.objectLike({
            Action: Match.arrayWith(['s3:GetBucket*', 's3:List*', 's3:DeleteObject*']),
            Effect: 'Allow',
            Resource: Match.anyValue(),
          }),
        ]),
      },
    });
  });

  test('Stack has the correct number of resources', () => {
    template.resourceCountIs('AWS::Lambda::Function', 2); // Main function + S3 auto-delete custom resource
    template.resourceCountIs('AWS::S3::Bucket', 1);
    template.resourceCountIs('AWS::Events::Rule', 1);
    template.resourceCountIs('AWS::SecretsManager::Secret', 1);
    template.resourceCountIs('AWS::SNS::Topic', 1);
    template.resourceCountIs('AWS::SNS::Subscription', 1);
    template.resourceCountIs('AWS::CloudWatch::Alarm', 3); // Error, Duration, Throttle
  });

  test('S3 Bucket has proper deletion policy', () => {
    template.hasResource('AWS::S3::Bucket', {
      DeletionPolicy: 'Delete',
      UpdateReplacePolicy: 'Delete',
    });
  });

  test('EventBridge Rule Created', () => {
    template.hasResourceProperties('AWS::Events::Rule', {
      ScheduleExpression: Match.stringLikeRegexp('rate\\(1 hour\\)'),
      State: 'ENABLED',
      Targets: Match.arrayWith([
        Match.objectLike({
          Arn: Match.anyValue(),
          Id: Match.anyValue(),
        }),
      ]),
    });
  });

  test('Lambda has appropriate IAM permissions', () => {
    // Check that there's at least one Lambda execution role
    const roles = template.findResources('AWS::IAM::Role');
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const lambdaRoles = Object.values(roles).filter((role: any) =>
      role.Properties?.AssumeRolePolicyDocument?.Statement?.some(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (stmt: any) => stmt.Principal?.Service === 'lambda.amazonaws.com'
      )
    );
    expect(lambdaRoles.length).toBeGreaterThan(0);
  });

  test('Secrets Manager Secret Created', () => {
    template.hasResourceProperties('AWS::SecretsManager::Secret', {
      Name: Match.stringLikeRegexp('camply-checker-.*-alert-email'),
      Description: 'Alert email for Camply checker notifications',
      GenerateSecretString: {
        SecretStringTemplate: '{"email":""}',
        GenerateStringKey: 'email',
        ExcludeCharacters: '"@/\\',
      },
    });
  });

  test('SNS Topic Created for Alerts', () => {
    template.hasResourceProperties('AWS::SNS::Topic', {
      DisplayName: 'Camply Lambda Alerts',
    });
  });

  test('SNS Email Subscription Created', () => {
    template.hasResourceProperties('AWS::SNS::Subscription', {
      Protocol: 'email',
      TopicArn: Match.anyValue(),
      Endpoint: Match.anyValue(),
    });
  });

  test('CloudWatch Error Alarm Created', () => {
    template.hasResourceProperties('AWS::CloudWatch::Alarm', {
      AlarmDescription: 'Camply Lambda function errors',
      ComparisonOperator: 'GreaterThanOrEqualToThreshold',
      EvaluationPeriods: 1,
      MetricName: 'Errors',
      Namespace: 'AWS/Lambda',
      Period: 300,
      Statistic: 'Sum',
      Threshold: 1,
      TreatMissingData: 'notBreaching',
    });
  });

  test('CloudWatch Duration Alarm Created', () => {
    template.hasResourceProperties('AWS::CloudWatch::Alarm', {
      AlarmDescription: 'Camply Lambda function taking too long',
      ComparisonOperator: 'GreaterThanThreshold',
      EvaluationPeriods: 1,
      MetricName: 'Duration',
      Namespace: 'AWS/Lambda',
      Period: 300,
      Statistic: 'Average',
      Threshold: 240000,
      TreatMissingData: 'notBreaching',
    });
  });

  test('CloudWatch Throttle Alarm Created', () => {
    template.hasResourceProperties('AWS::CloudWatch::Alarm', {
      AlarmDescription: 'Camply Lambda function throttled',
      ComparisonOperator: 'GreaterThanOrEqualToThreshold',
      EvaluationPeriods: 1,
      MetricName: 'Throttles',
      Namespace: 'AWS/Lambda',
      Period: 300,
      Statistic: 'Sum',
      Threshold: 1,
      TreatMissingData: 'notBreaching',
    });
  });

  test('Lambda has Secrets Manager permissions', () => {
    template.hasResourceProperties('AWS::IAM::Policy', {
      PolicyDocument: {
        Statement: Match.arrayWith([
          Match.objectLike({
            Action: ['secretsmanager:GetSecretValue', 'secretsmanager:DescribeSecret'],
            Effect: 'Allow',
            Resource: Match.anyValue(),
          }),
        ]),
      },
    });
  });

  test('All CloudWatch Alarms have SNS Actions', () => {
    const alarms = template.findResources('AWS::CloudWatch::Alarm');
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    Object.values(alarms).forEach((alarm: any) => {
      expect(alarm.Properties.AlarmActions).toBeDefined();
      expect(alarm.Properties.AlarmActions.length).toBeGreaterThan(0);
    });
  });
});
