#!/bin/bash
set -e

LAMBDA_NAME="CamplyStack-prod-LambdaFunction9233991D-ioXwYaVrK7uB"
LOG_GROUP="/aws/lambda/$LAMBDA_NAME"

echo "=== CAMPLY CHECKER DEBUG MONITOR ==="
echo "Started at: $(date)"
echo ""

# Wait for latest deployment
echo "1. Checking deployment status..."
DEPLOY_STATUS=$(gh run list --limit 1 --json conclusion | jq -r '.[0].conclusion')
echo "   Latest deployment: $DEPLOY_STATUS"

if [ "$DEPLOY_STATUS" != "success" ]; then
    echo "   ERROR: Deployment failed!"
    exit 1
fi

# Trigger Lambda manually
echo ""
echo "2. Triggering Lambda manually..."
aws lambda invoke --function-name "$LAMBDA_NAME" /tmp/lambda-response.json > /dev/null 2>&1 &
INVOKE_PID=$!

# Wait for execution to complete (max 2 minutes)
sleep 120
kill $INVOKE_PID 2>/dev/null || true

# Get the latest log stream
echo ""
echo "3. Analyzing recent logs..."
LATEST_STREAM=$(aws logs describe-log-streams \
    --log-group-name "$LOG_GROUP" \
    --order-by LastEventTime \
    --descending \
    --max-items 1 \
    --query 'logStreams[0].logStreamName' \
    --output text)

echo "   Latest log stream: $LATEST_STREAM"

# Extract key information
echo ""
echo "4. Key findings:"
echo ""

# Check if Lambda executed
EXEC_COUNT=$(aws logs filter-log-events \
    --log-group-name "$LOG_GROUP" \
    --log-stream-names "$LATEST_STREAM" \
    --filter-pattern "CAMPLY CHECKER" \
    --query 'events[*].message' \
    --output text | wc -l)

echo "   Lambda executions found: $EXEC_COUNT"

if [ "$EXEC_COUNT" -eq 0 ]; then
    echo "   ERROR: Lambda not executing!"
    echo ""
    echo "   Checking for errors..."
    aws logs filter-log-events \
        --log-group-name "$LOG_GROUP" \
        --log-stream-names "$LATEST_STREAM" \
        --filter-pattern "error" \
        --query 'events[*].message' \
        --output text | head -5
    exit 1
fi

# Check campground searches
echo ""
echo "   Campground searches:"
aws logs filter-log-events \
    --log-group-name "$LOG_GROUP" \
    --log-stream-names "$LATEST_STREAM" \
    --filter-pattern "Searching S Rav" \
    --query 'events[*].message' \
    --output text | grep -o "Searching.*" | head -3

# Check sites found
echo ""
echo "   Sites found:"
aws logs filter-log-events \
    --log-group-name "$LOG_GROUP" \
    --log-stream-names "$LATEST_STREAM" \
    --filter-pattern "total sites found" \
    --query 'events[*].message' \
    --output text | grep -o "[0-9]* total sites found.*" | head -5

# Check campground metadata matching
echo ""
echo "   Campground metadata matching (DEBUG):"
aws logs filter-log-events \
    --log-group-name "$LOG_GROUP" \
    --log-stream-names "$LATEST_STREAM" \
    --filter-pattern "Processing site" \
    --query 'events[*].message' \
    --output text | grep -o "campground_id=.*" | head -10

# Check notify results
echo ""
echo "   Notify results:"
NOTIFY_MSG=$(aws logs filter-log-events \
    --log-group-name "$LOG_GROUP" \
    --log-stream-names "$LATEST_STREAM" \
    --filter-pattern "notify" \
    --query 'events[*].message' \
    --output text | grep -i "notify" | tail -5)

echo "$NOTIFY_MSG"

# Check email status
echo ""
echo "   Email status:"
EMAIL_STATUS=$(aws logs filter-log-events \
    --log-group-name "$LOG_GROUP" \
    --log-stream-names "$LATEST_STREAM" \
    --filter-pattern "email" \
    --query 'events[*].message' \
    --output text | grep -i "email" | tail -3)

if [ -z "$EMAIL_STATUS" ]; then
    echo "   No email activity found"
else
    echo "$EMAIL_STATUS"
fi

echo ""
echo "=== ANALYSIS COMPLETE ==="
echo ""

# Determine root cause
if echo "$NOTIFY_MSG" | grep -q "No notify sites available"; then
    echo "ROOT CAUSE: Sites are being found but not added to notify_results"
    echo ""
    echo "LIKELY ISSUE: Campground metadata not matching or notify flag not set"
    echo ""
    echo "Next steps:"
    echo "1. Check if campground_id from camply matches config/campgrounds.json"
    echo "2. Verify get_campground_metadata() function is working"
    echo "3. Check if 'notify: true' is set for campground 766"
fi
