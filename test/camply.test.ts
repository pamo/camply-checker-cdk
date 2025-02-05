import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { CamplyStack } from '../lib/stacks/camply-stack';
import { Config } from '../lib/config';

describe('CamplyStack', () => {
  let app: cdk.App;
  let stack: CamplyStack;
  let template: Template;

  beforeEach(() => {
    app = new cdk.App();
    // Create test configuration
    const testConfig = new Config('dev');
    stack = new CamplyStack(app, 'TestStack', {
      config: testConfig,
      env: {
        account: '123456789012',
        region: 'us-west-2',
      },
    });
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
          EMAIL_SECRET_ARN: Match.anyValue(),
        },
      },
    });
  });

  test('EventBridge Rule Created', () => {
    template.hasResourceProperties('AWS::Events::Rule', {
      ScheduleExpression: Match.stringLikeRegexp('rate\\(60 minutes\\)'),
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
    template.hasResourceProperties('AWS::IAM::Role', {
      AssumeRolePolicyDocument: Match.objectLike({
        Statement: [
          {
            Action: 'sts:AssumeRole',
            Effect: 'Allow',
            Principal: {
              Service: 'lambda.amazonaws.com',
            },
          },
        ],
      }),
      ManagedPolicyArns: Match.arrayWith([
        Match.stringLikeRegexp('arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'),
      ]),
    });

    // Verify S3 permissions
    template.hasResourceProperties('AWS::IAM::Policy', {
      PolicyDocument: {
        Statement: Match.arrayWith([
          Match.objectLike({
            Action: [
              's3:GetObject*',
              's3:GetBucket*',
              's3:List*',
              's3:DeleteObject*',
              's3:PutObject*',
            ],
            Effect: 'Allow',
            Resource: Match.anyValue(),
          }),
        ]),
      },
    });
  });

  test('Stack has the correct number of resources', () => {
    // Update these numbers based on your actual resources
    template.resourceCountIs('AWS::Lambda::Function', 1);
    template.resourceCountIs('AWS::S3::Bucket', 1);
    template.resourceCountIs('AWS::Events::Rule', 1);
  });

  test('S3 Bucket has proper deletion policy', () => {
    template.hasResource('AWS::S3::Bucket', {
      DeletionPolicy: 'Delete',
      UpdateReplacePolicy: 'Delete',
    });
  });

  test('Lambda function has proper dependencies', () => {
    // Ensure Lambda depends on its role
    template.hasResource('AWS::Lambda::Function', {
      DependsOn: Match.arrayWith([Match.stringLikeRegexp('.*ServiceRole.*')]),
    });
  });
});
