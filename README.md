# Reveal Gallery

A web application for displaying and managing images from Reveal cameras with weather data integration.

## Project Structure

```
reveal_gallery/
├── src/
│   ├── api.py          # API endpoints for frontend
│   ├── app.py          # Main Flask application
│   ├── reveal_sync.py  # Reveal camera sync script
│   ├── templates/      # HTML templates
│   ├── static/         # Static assets (JS, CSS)
│   └── schema.sql      # Database schema
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

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
```

4. Initialize the database:
```bash
psql -U your_user -d reveal_gallery -f src/schema.sql
psql -U your_user -d reveal_gallery -f src/permissions.sql
```

## Development

- Run the API server: `python src/api.py`
- Run the sync script: `python src/reveal_sync.py`

## Deployment

The application is designed to be deployed with:
- Frontend: Served via Nginx
- Backend API: Flask application on port 8000
- Database: PostgreSQL
- Image Storage: DigitalOcean Spaces
