# Campground Configuration

This directory contains the configuration for campgrounds monitored by the camply checker.

## Configuration File: `campgrounds.json`

### Structure

```json
{
  "campgrounds": [
    {
      "id": 766,
      "name": "Steep Ravine",
      "provider": "ReserveCalifornia",
      "priority": 1,
      "enabled": true,
      "site_name_pattern": "cabin|site",
      "display_format": "site_and_loop",
      "filter": "hike-in"
    }
  ]
}
```

### Fields

- **id** (required): Campground ID from the provider (Recreation.gov or ReserveCalifornia)
- **name** (required): Display name for the campground in emails
- **provider** (required): Either "RecreationDotGov" or "ReserveCalifornia"
- **priority** (required): Lower numbers appear first in emails (1 = highest priority)
- **enabled** (required): Set to `false` to disable monitoring without removing the entry
- **site_name_pattern** (optional): Regex pattern for extracting site names
- **display_format** (optional): How to format site names in emails
  - `"simple"`: Basic site name display
  - `"site_and_loop"`: Extract "Site: 010, Loop: Sky" format
- **filter** (optional): Special filtering rules (e.g., "hike-in" for Point Reyes)

### Priority System

Campgrounds are sorted by priority in emails:
1. Steep Ravine (priority 1-2) - appears first
2. Point Reyes (priority 3) 
3. Other campgrounds (priority 4+)

### Adding New Campgrounds

1. Find the campground ID from the provider's website
2. Add entry to `campgrounds.json` with appropriate priority
3. Set `enabled: true` to start monitoring
4. Deploy changes with `npm run deploy:prod`

### Disabling Campgrounds

Set `enabled: false` to temporarily disable monitoring while keeping the configuration for future use.

### Deployment

Configuration changes are automatically included in deployments. The `sync-config.sh` script copies the config to the Lambda directory before deployment.
