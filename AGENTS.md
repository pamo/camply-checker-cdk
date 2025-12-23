# Camply Checker CDK

An AWS Lambda-based campsite availability checker that monitors popular California and national park campgrounds using the [camply](https://github.com/juftin/camply) library.

## What This Does

- **Monitors campgrounds** for availability using camply v0.33.1
- **Sends email notifications** when campsites become available
- **Runs on a schedule** via EventBridge (configurable interval)
- **Tracks multiple providers**: Recreation.gov and ReserveCalifornia
- **Includes monitoring** with CloudWatch alarms and SNS alerts
- **Simplified implementation** - No numpy conflicts, minimal dependencies

## Monitored Campgrounds

### ReserveCalifornia
- Steep Ravine (ID: 766)
- Steep Ravine Campgrounds (ID: 590) 
- Pantoll Campground (ID: 2009)
- Frank Valley Horse Campground (ID: 589)
- Bootjack Campground (ID: 2008)
- Julia Pfeiffer Burns (ID: 518)

### Recreation.gov
- Sardine Peak Lookout (ID: 252037)

## Architecture

```
EventBridge Rule → Lambda Function → Email Notifications
                      ↓
                 CloudWatch Metrics → SNS Alerts
```

## Prerequisites

- Node.js >= 18.0.0
- AWS CLI configured with appropriate credentials
- AWS CDK installed globally: `npm install -g aws-cdk`

## Configuration

Create a `.env` file in the root directory:

```bash
# Email Configuration (Required)
EMAIL_TO_ADDRESS="your-email@example.com"
EMAIL_USERNAME="your-smtp-username"
EMAIL_PASSWORD="your-smtp-password"
EMAIL_SMTP_SERVER="smtp.gmail.com"
EMAIL_SMTP_PORT="587"
EMAIL_FROM_ADDRESS="camply@your-domain.com"
EMAIL_SUBJECT_LINE="Camply Notification"

# Search Configuration
SEARCH_WINDOW_DAYS="14"

# Alert Configuration
ALERT_EMAIL_ADDRESS="alerts@your-domain.com"
```

### Email Setup Options

**Gmail:**
```bash
EMAIL_SMTP_SERVER="smtp.gmail.com"
EMAIL_SMTP_PORT="587"
EMAIL_USERNAME="your-gmail@gmail.com"
EMAIL_PASSWORD="your-app-password"  # Use App Password, not regular password
```

**Outlook:**
```bash
EMAIL_SMTP_SERVER="smtp-mail.outlook.com"
EMAIL_SMTP_PORT="587"
EMAIL_USERNAME="your-email@outlook.com"
EMAIL_PASSWORD="your-password"
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

## Recent Updates (v2.0 - Simplified)

This repository has been updated with a simplified implementation that:
- ✅ **Fixes numpy dependency issues** - Uses lightweight Python 3.11 base image
- ✅ **Reduces complexity** - Minimal dependencies (camply + boto3 only)
- ✅ **Improves reliability** - Uses correct camply v0.33.1 API patterns
- ✅ **Reduces costs** - Lower memory usage (256MB vs 512MB)
- ✅ **Faster deployments** - Smaller Docker image, faster cold starts

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
    {'provider': 'RecreationDotGov', 'campgrounds': [YOUR_CAMPGROUND_ID]},
    
    # ReserveCalifornia campgrounds  
    {'provider': 'ReserveCalifornia', 'campgrounds': [YOUR_CAMPGROUND_ID]},
]
```

## Monitoring & Alerts

The system includes CloudWatch alarms for:
- Lambda function errors
- Function timeouts (>3 minutes)
- Function throttling
- Email delivery failures

Alerts are sent to the `ALERT_EMAIL_ADDRESS` configured in your `.env` file.

## Troubleshooting

### Common Issues

**Lambda timeout:**
- Current timeout is 3 minutes (reduced from 5)
- Reduce number of campgrounds being checked if needed

**Email delivery failures:**
- Verify SMTP credentials
- Check if using App Passwords for Gmail
- Ensure firewall allows SMTP traffic

**No availability notifications:**
- Check CloudWatch logs for search results
- Verify campground IDs are correct
- Test with shorter search window

### Viewing Logs
```bash
# View Lambda logs
aws logs tail /aws/lambda/CamplyStack-Lambda --follow

# View specific log group
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/CamplyStack"
```

### Manual Testing
```bash
# Test Lambda function directly
aws lambda invoke --function-name CamplyStack-Lambda response.json
cat response.json
```

## Re-enabling After Manual Disable

If you manually disabled EventBridge rules or CloudWatch alarms:

### Option 1: Redeploy (Recommended)
```bash
npm run build
npm run deploy:dev  # or deploy:prod
```

### Option 2: Manual Re-enable via Console
1. **EventBridge**: Go to EventBridge → Rules → Enable the rule
2. **CloudWatch**: Go to CloudWatch → Alarms → Select alarms → Actions → Enable

### Option 3: CLI Re-enable
```bash
# Re-enable EventBridge rule
aws events enable-rule --name "CamplyStack-ScheduleRule"

# Re-enable CloudWatch alarms
aws cloudwatch enable-alarm-actions --alarm-names "CamplyStack-ErrorAlarm"
```

## Development

### Local Testing
```bash
# Test camply functionality
python test_simplified.py

# Test specific campgrounds (requires virtual environment)
python3 -m venv test_env
source test_env/bin/activate
pip install camply==0.33.1
python test_simplified.py
```

### Updating Campgrounds
1. Find campground IDs using camply CLI or recreation.gov
2. Update `lambda/index.py`
3. Redeploy: `npm run deploy:dev`

## Cost Estimation

**Monthly costs (approximate):**
- Lambda: $0.15 (reduced from $0.20 due to lower memory)
- CloudWatch: $0.30 (reduced logging)
- SNS: $0.50 (email notifications)
- **Total: ~$0.95/month** (down from $1.20)

## Security Notes

- SMTP credentials are stored as environment variables
- Consider using AWS Secrets Manager for production
- Lambda has minimal IAM permissions (S3, CloudWatch, SNS only)

## Support

For issues with:
- **Camply library**: [juftin/camply GitHub](https://github.com/juftin/camply)
- **AWS CDK**: [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- **This implementation**: Check CloudWatch logs and GitHub issues
