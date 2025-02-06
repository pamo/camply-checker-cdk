import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export class GithubActionsStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Create the GitHub OIDC provider if it doesn't exist
    const githubProvider = new iam.OpenIdConnectProvider(this, 'GithubProvider', {
      url: 'https://token.actions.githubusercontent.com',
      clientIds: ['sts.amazonaws.com'],
      thumbprints: ['6938fd4d98bab03faadb97b34396831e3780aea1'],
    });

    // Create the role that GitHub Actions will assume
    const githubActionsRole = new iam.Role(this, 'GithubActionsRole', {
      roleName: 'GithubActionsCamplyRole',
      assumedBy: new iam.WebIdentityPrincipal(githubProvider.openIdConnectProviderArn, {
        StringLike: {
          'token.actions.githubusercontent.com:sub': 'repo:pamo/camply-checker-cdk:*',
        },
        StringEquals: {
          'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com',
        },
      }),
    });

    // Add required permissions for CDK deployments
    githubActionsRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'cloudformation:*',
          'lambda:*',
          'iam:*',
          'events:*',
          's3:*',
          'cloudwatch:*',
          'logs:*',
        ],
        resources: ['*'], // In production, scope this to specific resources
      })
    );

    // Output the role ARN
    new cdk.CfnOutput(this, 'GithubActionsRoleArn', {
      value: githubActionsRole.roleArn,
      description: 'ARN of the IAM role for GitHub Actions',
    });
  }
}
