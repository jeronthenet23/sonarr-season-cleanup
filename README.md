# sonarr-season-cleanup

Automatically unmonitors and deletes older seasons of TV shows in Sonarr, keeping only the most recent season on disk.

Useful for ongoing shows where you only want the current season — saves significant disk space over time.

## How it works

1. Tag any series in Sonarr with `keep-latest`
2. Run this script (manually or via cron)
3. It finds all tagged series, keeps the newest season, unmonitors and deletes everything older

## Configuration

Set these environment variables before running:

| Variable | Default | Description |
|----------|---------|-------------|
| SONARR_URL | http://localhost:8989 | Base URL of your Sonarr instance |
| SONARR_API_KEY | required | Your Sonarr API key |
| KEEP_LATEST_TAG | keep-latest | Tag name to look for in Sonarr |
| LOG_FILE | /tmp/sonarr_cleanup.log | Path to log file |

## Usage

Run with dry-run first to preview changes:

    SONARR_URL=http://localhost:8989 SONARR_API_KEY=yourkey python3 sonarr_cleanup.py --dry-run

Then run for real:

    SONARR_URL=http://localhost:8989 SONARR_API_KEY=yourkey python3 sonarr_cleanup.py

## Cron example

Run on the 1st of every month at 3am:

    0 3 1 * * SONARR_URL=http://localhost:8989 SONARR_API_KEY=yourkey python3 /path/to/sonarr_cleanup.py

## Requirements

    pip install requests

## License

MIT
