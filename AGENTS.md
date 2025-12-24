# Camply Checker CDK

An AWS Lambda-based campsite availability checker that monitors popular California and national park campgrounds using the [camply](https://github.com/juftin/camply) library.

## What This Does

- **Monitors campgrounds** for availability using camply v0.33.1
- **Sends email notifications** when campsites become available
- **Runs on a schedule** via EventBridge (every 30 minutes)
- **Tracks multiple providers**: Recreation.gov and ReserveCalifornia
- **Includes monitoring** with CloudWatch alarms and GitHub Actions auto-recovery
- **Email deduplication** - Only sends notifications when availability actually changes
- **Smart prioritization** - Steep Ravine sites appear first in emails

## Monitored Campgrounds

### ReserveCalifornia
- Steep Ravine (ID: 766) - **Prioritized**
- Steep Ravine Campgrounds (ID: 590) - **Prioritized**
- Pantoll Campground (ID: 2009)
- Frank Valley Horse Campground (ID: 589)
- Bootjack Campground (ID: 2008)
- Julia Pfeiffer Burns (ID: 518)

### Recreation.gov
- Sardine Peak Lookout (ID: 252037)
- Point Reyes National Seashore Campground (ID: 233359) - **Hike-in sites only**

## Architecture

```
EventBridge Rule → Lambda Function → Email Notifications
                      ↓                    ↓
                 CloudWatch Metrics    S3 Cache (deduplication)
                      ↓
              GitHub Actions Auto-Recovery
```

## Prerequisites

- Node.js >= 18.0.0
- AWS CLI configured with appropriate credentials
- AWS CDK installed globally: `npm install -g aws-cdk`

## Configuration

Create a `.env` file in the root directory:

```bash
# Email Configuration (Required)
EMAIL_TO_ADDRESS="your-email@example.com,second-email@example.com"
EMAIL_USERNAME="your-smtp-username"
EMAIL_PASSWORD="your-smtp-password"
EMAIL_SMTP_SERVER="smtp.gmail.com"
EMAIL_SMTP_PORT="587"
EMAIL_FROM_ADDRESS="camply@your-domain.com"
EMAIL_SUBJECT_LINE="⛺️ Camply Update ⛺️"

# Search Configuration
SEARCH_WINDOW_DAYS="90"
```

### Email Setup Options

**Gmail:**
```bash
EMAIL_SMTP_SERVER="smtp.gmail.com"
EMAIL_SMTP_PORT="587"
EMAIL_USERNAME="your-gmail@gmail.com"
EMAIL_PASSWORD="your-app-password"  # Use App Password, not regular password
```

## Deployment

### 1. Install Dependencies
```bash
npm install
```

### 2. Bootstrap CDK (first time only)
```bash
npm run bootstrap
```

### 3. Build Project
```bash
npm run build
```

### 4. Deploy to Development
```bash
npm run deploy:dev
```

### 5. Deploy to Production
```bash
npm run deploy:prod
```

## Auto-Recovery System

The system includes GitHub Actions-based auto-recovery that:
- **Monitors every 15 minutes** for Docker architecture failures
- **Automatically fixes** Lambda deployment issues
- **Sends recovery notifications** via direct SMTP
- **Works while camping** - No manual intervention needed

### Setup GitHub Actions Auto-Recovery

1. Add these GitHub repository secrets:
   - `AWS_ACCESS_KEY_ID`: Your AWS access key
   - `AWS_SECRET_ACCESS_KEY`: Your AWS secret key
   - `EMAIL_USERNAME`: Your Gmail username
   - `EMAIL_PASSWORD`: Your Gmail app password
   - `EMAIL_TO_ADDRESS`: Notification recipients
   - `EMAIL_FROM_ADDRESS`: Sender email

2. The workflow automatically triggers every 15 minutes to check system health

## Recent Updates (v3.0 - Production Ready)

This repository has been updated with production-ready features:
- ✅ **Email deduplication** - Uses S3 cache to prevent duplicate notifications
- ✅ **Smart prioritization** - Steep Ravine sites appear first using campground IDs
- ✅ **Combined notifications** - Single email per run instead of separate emails per provider
- ✅ **Point Reyes filtering** - Only includes hike-in sites, excludes boat-in
- ✅ **Auto-recovery system** - GitHub Actions automatically fixes Docker issues
- ✅ **Simplified monitoring** - Removed problematic SNS, uses direct SMTP
- ✅ **Architecture resilience** - Handles Docker cache pollution automatically

## Configuration Options

### Schedule Frequency
Edit `lib/config.ts` to change the check frequency:
```typescript
scheduleRate: 30, // Check every 30 minutes
```

### Add/Remove Campgrounds
Edit `lambda/index.py`:
```python
campgrounds = [
    # Recreation.gov campgrounds
    {'provider': 'RecreationDotGov', 'campgrounds': [252037, 233359]},
    
    # ReserveCalifornia campgrounds  
    {'provider': 'ReserveCalifornia', 'campgrounds': [766, 590, 2009, 589, 2008, 518]},
]
```

## Monitoring & Alerts

The system includes:
- **CloudWatch alarms** for Lambda errors, timeouts, and throttling
- **GitHub Actions monitoring** every 15 minutes
- **Auto-recovery** for Docker architecture issues
- **Direct email notifications** for system recovery

## Troubleshooting

### Common Issues

**Docker architecture errors:**
- **Auto-fixed** by GitHub Actions within 15 minutes
- Manual fix: `docker system prune -f && npm run deploy:prod`

**No availability notifications:**
- Check CloudWatch logs for search results
- Verify campground IDs are correct
- Clear S3 cache if needed: `aws s3 rm s3://bucket/last_sent_*.txt`

### Viewing Logs
```bash
# View Lambda logs
AWS_PROFILE=camply-checker aws logs tail /aws/lambda/CamplyStack-prod-LambdaFunction... --follow

# Check recent executions
AWS_PROFILE=camply-checker aws logs filter-log-events --log-group-name "/aws/lambda/CamplyStack-prod-LambdaFunction..." --since 1h
```

### Manual Testing
```bash
# Test Lambda function directly
AWS_PROFILE=camply-checker aws lambda invoke --function-name CamplyStack-prod-LambdaFunction... response.json
cat response.json

# Clear cache to force new email
AWS_PROFILE=camply-checker aws s3 rm s3://bucket/last_sent_RecreationDotGov_sites.txt
AWS_PROFILE=camply-checker aws s3 rm s3://bucket/last_sent_ReserveCalifornia_sites.txt
```

## Development

### Local Testing
```bash
# Test camply functionality
python3 -m venv test_env
source test_env/bin/activate
pip install camply==0.33.1
python research_campground.py
```

### Updating Campgrounds
1. Find campground IDs using camply CLI or recreation.gov
2. Update `lambda/index.py`
3. Redeploy: `npm run deploy:prod`

## Cost Estimation

**Monthly costs (approximate):**
- Lambda: $0.15 (256MB memory, 30-min intervals)
- CloudWatch: $0.20 (reduced logging)
- S3: $0.05 (cache storage)
- GitHub Actions: Free (within limits)
- **Total: ~$0.40/month** (reduced from $0.95 due to SNS removal)

## Security Notes

- SMTP credentials stored as environment variables
- AWS credentials rotated regularly
- Lambda has minimal IAM permissions (S3, CloudWatch only)
- GitHub Actions uses repository secrets for credentials

## Support

For issues with:
- **Camply library**: [juftin/camply GitHub](https://github.com/juftin/camply)
- **AWS CDK**: [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- **Auto-recovery**: Check GitHub Actions workflow logs
