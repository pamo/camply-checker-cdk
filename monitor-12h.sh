#!/bin/bash
# 12-hour monitoring script for Camply Checker

LAMBDA_NAME="CamplyStack-prod-LambdaFunction9233991D-ioXwYaVrK7uB"
LOG_FILE="/tmp/camply-monitor-$(date +%Y%m%d-%H%M%S).log"
DURATION_HOURS=12
END_TIME=$(($(date +%s) + (DURATION_HOURS * 3600)))

echo "=== CAMPLY CHECKER 12-HOUR MONITOR ===" | tee -a "$LOG_FILE"
echo "Started: $(date)" | tee -a "$LOG_FILE"
echo "Will monitor until: $(date -r $END_TIME)" | tee -a "$LOG_FILE"
echo "Log file: $LOG_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

EXECUTION_COUNT=0
EMAIL_SENT_COUNT=0
DEDUPE_SKIP_COUNT=0
ERROR_COUNT=0

while [ $(date +%s) -lt $END_TIME ]; do
    CURRENT_TIME=$(date "+%Y-%m-%d %H:%M:%S")
    
    # Get logs from last 35 minutes (to catch the 30-min interval)
    LOGS=$(aws logs tail /aws/lambda/$LAMBDA_NAME --since 35m --format short 2>&1)
    
    # Check for new executions
    NEW_EXECUTIONS=$(echo "$LOGS" | grep "FACILITY MATCHING ENABLED" | wc -l)
    if [ "$NEW_EXECUTIONS" -gt "$EXECUTION_COUNT" ]; then
        EXECUTION_COUNT=$NEW_EXECUTIONS
        echo "[$CURRENT_TIME] ✓ Lambda executed (total: $EXECUTION_COUNT)" | tee -a "$LOG_FILE"
        
        # Check if email was sent
        if echo "$LOGS" | tail -50 | grep -q "Sent email for.*notify sites"; then
            EMAIL_SENT_COUNT=$((EMAIL_SENT_COUNT + 1))
            SITE_COUNT=$(echo "$LOGS" | tail -50 | grep "Sent email for" | tail -1 | grep -o "[0-9]* notify sites" | grep -o "[0-9]*")
            echo "[$CURRENT_TIME]   📧 Email sent for $SITE_COUNT sites" | tee -a "$LOG_FILE"
        elif echo "$LOGS" | tail -50 | grep -q "Skipping email - no changes detected"; then
            DEDUPE_SKIP_COUNT=$((DEDUPE_SKIP_COUNT + 1))
            SITE_COUNT=$(echo "$LOGS" | tail -50 | grep "Skipping email" | tail -1 | grep -o "[0-9]* notify sites" | grep -o "[0-9]*")
            echo "[$CURRENT_TIME]   ⏭  Skipped (deduped) - $SITE_COUNT sites unchanged" | tee -a "$LOG_FILE"
        elif echo "$LOGS" | tail -50 | grep -q "No notify sites available"; then
            echo "[$CURRENT_TIME]   ℹ️  No notify sites found" | tee -a "$LOG_FILE"
        fi
        
        # Check for errors
        if echo "$LOGS" | tail -100 | grep -qi "error\|exception\|failed"; then
            ERROR_COUNT=$((ERROR_COUNT + 1))
            echo "[$CURRENT_TIME]   ⚠️  Error detected in logs" | tee -a "$LOG_FILE"
        fi
    fi
    
    # Summary every 2 hours
    ELAPSED_HOURS=$(( ($(date +%s) - (END_TIME - (DURATION_HOURS * 3600))) / 3600 ))
    if [ $((ELAPSED_HOURS % 2)) -eq 0 ] && [ $ELAPSED_HOURS -gt 0 ]; then
        REMAINING_HOURS=$((DURATION_HOURS - ELAPSED_HOURS))
        if [ $REMAINING_HOURS -gt 0 ]; then
            echo "" | tee -a "$LOG_FILE"
            echo "[$CURRENT_TIME] === ${ELAPSED_HOURS}h Summary (${REMAINING_HOURS}h remaining) ===" | tee -a "$LOG_FILE"
            echo "  Executions: $EXECUTION_COUNT" | tee -a "$LOG_FILE"
            echo "  Emails sent: $EMAIL_SENT_COUNT" | tee -a "$LOG_FILE"
            echo "  Deduped: $DEDUPE_SKIP_COUNT" | tee -a "$LOG_FILE"
            echo "  Errors: $ERROR_COUNT" | tee -a "$LOG_FILE"
            echo "" | tee -a "$LOG_FILE"
        fi
    fi
    
    # Check every 5 minutes
    sleep 300
done

echo "" | tee -a "$LOG_FILE"
echo "=== FINAL REPORT ===" | tee -a "$LOG_FILE"
echo "Completed: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "Total executions: $EXECUTION_COUNT (expected: ~24)" | tee -a "$LOG_FILE"
echo "Emails sent: $EMAIL_SENT_COUNT" | tee -a "$LOG_FILE"
echo "Deduped skips: $DEDUPE_SKIP_COUNT" | tee -a "$LOG_FILE"
echo "Errors: $ERROR_COUNT" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

if [ $ERROR_COUNT -gt 0 ]; then
    echo "⚠️  ISSUES DETECTED - Check logs for errors" | tee -a "$LOG_FILE"
elif [ $EXECUTION_COUNT -lt 20 ]; then
    echo "⚠️  LOW EXECUTION COUNT - Lambda may not be running on schedule" | tee -a "$LOG_FILE"
elif [ $EMAIL_SENT_COUNT -eq 0 ] && [ $DEDUPE_SKIP_COUNT -eq 0 ]; then
    echo "⚠️  NO EMAILS OR DEDUPE - No notify sites found for 12 hours" | tee -a "$LOG_FILE"
else
    echo "✅ SYSTEM HEALTHY - Deduplication working correctly" | tee -a "$LOG_FILE"
fi

echo "" | tee -a "$LOG_FILE"
echo "Full log saved to: $LOG_FILE" | tee -a "$LOG_FILE"
