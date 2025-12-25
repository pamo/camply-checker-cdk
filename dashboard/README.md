# Camply Dashboard

A web dashboard that displays campsite availability in the same format as the email notifications, with filtering capabilities.

## Local Development

### Quick Start
```bash
# Generate dashboard with sample data
python generate_dashboard.py --sample

# Open in browser
open dashboard/index.html
```

### Development Workflow

1. **Edit the template:** `dashboard/template.html`
2. **Regenerate:** `python generate_dashboard.py --sample`
3. **Preview:** `open dashboard/index.html`

### Using Real Data

If you have a JSON file with real campsite data:
```bash
python generate_dashboard.py --input sites_data.json
open dashboard/index.html
```

## Production Dashboard

The dashboard is automatically generated and uploaded to S3 every time the Lambda function runs. Access it at the URL shown in CDK deployment outputs.

## Features

- **Email Preview**: Shows exactly what the email notification looks like
- **Area Filter**: Filter campsites by recreation area  
- **Date Filter**: Filter by date range
- **Real-time Updates**: Dashboard regenerated with each Lambda run
- **Responsive Design**: Works on desktop and mobile

## File Structure

```
dashboard/
├── template.html          # Source template (edit this)
└── index.html            # Generated dashboard (git ignored)

generate_dashboard.py     # Local generator script
```

## Template Placeholders

- `{{LAST_UPDATED}}` - Timestamp of last update
- `{{TOTAL_SITES}}` - Total number of available sites
- `{{TOTAL_AREAS}}` - Total number of recreation areas
- `{{EMAIL_CONTENT}}` - HTML content of the email preview
- `{{SITES_DATA}}` - JSON data for JavaScript filtering

## Deployment

Dashboard automatically deploys to S3 when Lambda runs. No manual deployment needed.
