import * as cdk from 'aws-cdk-lib';
import { CamplyStack } from '../lib/stacks/camply-stack';
import { GithubActionsStack } from '../lib/stacks/github-actions-stack';
import { Config } from '../lib/config';

const app = new cdk.App();

// Load configuration based on environment
const env = app.node.tryGetContext('env') || 'dev';
const config = new Config(env);

// Deploy stacks with environment configuration
new CamplyStack(app, `CamplyStack-${env}`, {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
  config: config,
});

// Only deploy GitHub Actions role in development account
if (env === 'dev') {
  new GithubActionsStack(app, 'GithubActionsStack', {
    env: {
      account: process.env.CDK_DEFAULT_ACCOUNT,
      region: process.env.CDK_DEFAULT_REGION,
    },
  });
}
