# Reveal Gallery

A web application for displaying and managing images from Reveal cameras with weather data integration and AI analysis.

## Project Structure

```
reveal_gallery/
├── src/
│   ├── api.py                    # API endpoints for frontend
│   ├── app.py                    # Main Flask application
│   ├── reveal_sync.py            # Reveal camera sync script
│   ├── reveal_analyze.py         # AI image analysis
│   ├── analyze_untagged.py       # Process images without tags
│   ├── analyze_all.py            # Reprocess all images
│   ├── backup_db.sh             # Database backup script
│   ├── run_sync.sh              # Automated sync wrapper
│   ├── run_analyze.sh           # Manual analysis trigger
│   ├── templates/                # HTML templates
│   ├── static/                  # Static assets (JS, CSS)
│   └── schema.sql               # Database schema
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## Core Components

### Sync Process
- `reveal_sync.py`: Downloads new images from Reveal camera system
  - Authenticates with Reveal
  - Downloads new images
  - Extracts metadata (weather, location, timestamp)
  - Uploads to Digital Ocean Spaces
  - Stores data in PostgreSQL

- `run_sync.sh`: Automated sync script (runs every 30 minutes via cron)
  - Downloads new images
  - Triggers analysis for new images
  - Falls back to checking for untagged images

### Image Analysis
- `reveal_analyze.py`: Core analysis functionality
  - Uses Google Gemini AI for image analysis
  - Identifies and counts wildlife
  - Creates standardized tags
  - Supports both new and specific images

### Analysis Tools
- `analyze_untagged.py`: Process images without tags
  - Finds images without any tags
  - Processes in batches of 20
  - Shows progress and remaining count

- `analyze_all.py`: Reprocess all images
  - Complete reanalysis of all images
  - Use with caution (API costs)

### Utility Scripts
- `backup_db.sh`: Daily database backup
  - Backs up schema and data separately
  - Compresses backups
  - Maintains 7-day rotation

## Setup

1. Create and activate a Python virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables in `.env`:
```
REVEAL_EMAIL=your_email
REVEAL_PASSWORD=your_password
DB_NAME=reveal_gallery
DB_USER=reveal_user
DB_PASSWORD=your_password
DB_HOST=localhost
DO_SPACES_KEY=your_key
DO_SPACES_SECRET=your_secret
DO_SPACE_NAME=your_space
GEMINI_API_KEY=your_key
```

4. Initialize the database:
```bash
psql -U your_user -d reveal_gallery -f src/schema.sql
psql -U your_user -d reveal_gallery -f src/permissions.sql
```

## Cron Jobs
```bash
# Every 30 minutes: Sync and analyze new images
0,30 * * * * /var/www/reveal_gallery/src/run_sync.sh

# Midnight: Clean up old logs
0 0 * * * cd /var/www/reveal_gallery/src && ./cleanup_logs.py

# 12:30 AM: Database backup
30 0 * * * /var/www/reveal_gallery/src/backup_db.sh
```

## Manual Operations

### Tag Management
```bash
# Process untagged images
python3 src/analyze_untagged.py

# Remove specific tags via API
DELETE /reveal_gallery/api/images/{image_id}/tags/{tag_name}
```

### Database Backup/Restore
```bash
# Manual backup
./src/backup_db.sh

# Restore from backup
gunzip -c backup_file.sql.gz | psql -U reveal_user -d reveal_gallery
```

## API Endpoints

- GET `/reveal_gallery/api/images`: Get images with filters
  - Query params: sort_by, sort_order, start_date, end_date, tags
- GET `/reveal_gallery/api/tags`: Get available tags
- DELETE `/reveal_gallery/api/images/{id}/tags/{tag}`: Remove specific tag

## Deployment

The application is designed to be deployed with:
- Frontend: Served via Nginx
- Backend API: Flask application on port 8000
- Database: PostgreSQL
- Image Storage: DigitalOcean Spaces
- Cron: Automated sync and backup jobs

## Important Notes
- Tag removal is permanent
- Analysis runs automatically after new images
- Backups rotate every 7 days
- Images are stored in Digital Ocean Spaces
- The sync process runs every 30 minutes
- Manual analysis tools should be used with caution (API costs)
