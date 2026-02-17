#!/bin/bash
set -e

LAMBDA_NAME="CamplyStack-prod-LambdaFunction9233991D-ioXwYaVrK7uB"
LOG_GROUP="/aws/lambda/$LAMBDA_NAME"

echo "=== AUTOMATED CAMPLY CHECKER INVESTIGATION ==="
echo "Started at: $(date)"
echo ""

# Step 1: Wait for deployment
echo "Step 1: Waiting for GitHub Actions deployment..."
sleep 30
for i in {1..12}; do
    STATUS=$(gh run list --limit 1 --json conclusion,status | jq -r '.[0] | "\(.status):\(.conclusion)"')
    echo "  Attempt $i/12: $STATUS"
    
    if [[ "$STATUS" == "completed:success" ]]; then
        echo "  ✓ Deployment successful!"
        break
    elif [[ "$STATUS" == "completed:failure" ]]; then
        echo "  ✗ Deployment failed!"
        echo ""
        echo "Checking CloudFormation errors..."
        aws cloudformation describe-stack-events --stack-name CamplyStack-prod --max-items 5 \
            --query 'StackEvents[?ResourceStatus==`UPDATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
            --output text
        exit 1
    fi
    
    sleep 15
done

# Step 2: Verify Lambda was updated
echo ""
echo "Step 2: Verifying Lambda code was updated..."
LAST_MODIFIED=$(aws lambda get-function --function-name "$LAMBDA_NAME" \
    --query 'Configuration.LastModified' --output text)
echo "  Lambda last modified: $LAST_MODIFIED"

# Step 3: Wait for next scheduled run (EventBridge runs every 30 min)
echo ""
echo "Step 3: Waiting for next Lambda execution (max 3 minutes)..."
INITIAL_TIME=$(date +%s)

for i in {1..18}; do
    sleep 10
    
    # Check for recent execution
    RECENT_LOGS=$(aws logs tail "$LOG_GROUP" --since 2m --format short 2>&1 | grep "CAMPLY CHECKER" | wc -l)
    
    if [ "$RECENT_LOGS" -gt 0 ]; then
        echo "  ✓ Lambda executed!"
        break
    fi
    
    ELAPSED=$(($(date +%s) - INITIAL_TIME))
    echo "  Waiting... (${ELAPSED}s elapsed)"
done

# Step 4: Analyze logs
echo ""
echo "Step 4: Analyzing execution logs..."
echo ""

# Get logs from last 5 minutes
LOGS=$(aws logs tail "$LOG_GROUP" --since 5m --format short 2>&1)

# Check for Steep Ravine searches
echo "  Steep Ravine searches:"
echo "$LOGS" | grep "Searching S Rav Cabin Area" | tail -3 | sed 's/^/    /'

# Check for sites found
echo ""
echo "  Sites found for Steep Ravine:"
echo "$LOGS" | grep -A1 "Searching S Rav Cabin Area" | grep "total sites found" | tail -3 | sed 's/^/    /'

# Check for debug output (campground matching)
echo ""
echo "  Debug: Campground metadata matching:"
DEBUG_OUTPUT=$(echo "$LOGS" | grep "Processing site.*campground_id=766" | head -5)
if [ -z "$DEBUG_OUTPUT" ]; then
    echo "    ⚠ No debug output found - code may not be deployed yet"
else
    echo "$DEBUG_OUTPUT" | sed 's/^/    /'
fi

# Check notify results
echo ""
echo "  Notify results:"
NOTIFY_OUTPUT=$(echo "$LOGS" | grep -i "notify" | tail -5)
if [ -z "$NOTIFY_OUTPUT" ]; then
    echo "    No notify messages found"
else
    echo "$NOTIFY_OUTPUT" | sed 's/^/    /'
fi

# Check email status
echo ""
echo "  Email status:"
EMAIL_OUTPUT=$(echo "$LOGS" | grep -iE "email|sent" | tail -3)
if [ -z "$EMAIL_OUTPUT" ]; then
    echo "    No email activity"
else
    echo "$EMAIL_OUTPUT" | sed 's/^/    /'
fi

# Step 5: Root cause analysis
echo ""
echo "=== ROOT CAUSE ANALYSIS ==="
echo ""

if echo "$LOGS" | grep -q "No notify sites available"; then
    echo "FINDING: Sites found but NOT added to notify_results"
    echo ""
    
    if [ -z "$DEBUG_OUTPUT" ]; then
        echo "ISSUE: Debug logging not present - Lambda code not updated"
        echo "ACTION NEEDED: Force rebuild or check CDK asset hashing"
    else
        # Parse debug output to see why sites aren't matching
        if echo "$DEBUG_OUTPUT" | grep -q "meta=False"; then
            echo "ISSUE: Campground metadata not found (meta=False)"
            echo "CAUSE: get_campground_metadata() not matching campground_id=766"
            echo "ACTION NEEDED: Check campgrounds.json structure and matching logic"
        elif echo "$DEBUG_OUTPUT" | grep -q "notify=False"; then
            echo "ISSUE: Notify flag is False"
            echo "CAUSE: 'notify: true' not set in config/campgrounds.json for ID 766"
            echo "ACTION NEEDED: Verify campgrounds.json has notify:true for campground 766"
        else
            echo "ISSUE: Unknown - debug output present but unclear"
            echo "Debug data:"
            echo "$DEBUG_OUTPUT" | sed 's/^/  /'
        fi
    fi
elif echo "$LOGS" | grep -q "Sent email"; then
    echo "SUCCESS: Emails are being sent!"
    echo "System is working correctly."
else
    echo "ISSUE: No clear indication of problem"
    echo "Possible causes:"
    echo "  - Lambda not executing on schedule"
    echo "  - No sites available for notify campgrounds"
    echo "  - Logs not captured properly"
fi

echo ""
echo "=== INVESTIGATION COMPLETE ==="
echo "Finished at: $(date)"
