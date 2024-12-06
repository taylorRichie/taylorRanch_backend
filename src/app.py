from flask import Flask, jsonify, request # type: ignore
from flask_cors import CORS # type: ignore
import psycopg2 # type: ignore
from psycopg2.extras import RealDictCursor # type: ignore
import os
from dotenv import load_dotenv # type: ignore
from datetime import datetime
from typing import List, Optional

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)

app = Flask(__name__)
CORS(app)

# Create a Blueprint for our API
from flask import Blueprint
api = Blueprint('api', __name__, url_prefix='/reveal_gallery/api')

def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST', 'localhost')
    )

@api.route('/locations')
def get_locations():
    """Get unique locations for the filter dropdown"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT DISTINCT primary_location, secondary_location
            FROM images
            WHERE primary_location IS NOT NULL
            ORDER BY primary_location, secondary_location
        """)
        
        locations = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify(locations)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api.route('/images')
def get_images():
    try:
        # Pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        offset = (page - 1) * per_page

        # Filter parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        location = request.args.get('location')
        
        # Sorting parameters
        sort_by = request.args.get('sort_by', 'capture_time')  # Default sort by capture time
        sort_order = request.args.get('sort_order', 'desc')    # Default to newest first
        
        # Validate sort parameters
        valid_sort_fields = ['capture_time', 'temperature', 'created_at']
        if sort_by not in valid_sort_fields:
            sort_by = 'capture_time'
        if sort_order.lower() not in ['asc', 'desc']:
            sort_order = 'desc'

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Build the WHERE clause and parameters
        where_clauses: List[str] = []
        params: List[any] = []
        
        if start_date:
            where_clauses.append("capture_time >= %s")
            params.append(start_date)
            
        if end_date:
            where_clauses.append("capture_time <= %s")
            params.append(end_date)
            
        if location:
            where_clauses.append("(primary_location = %s OR secondary_location = %s)")
            params.extend([location, location])
            
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Get total count with filters
        count_sql = f"SELECT COUNT(*) FROM images WHERE {where_sql}"
        cur.execute(count_sql, params)
        total_images = cur.fetchone()['count']
        
        # Build the final query
        query = f"""
            SELECT id, reveal_id, cdn_url, capture_time,
                   primary_location, secondary_location,
                   temperature, temperature_unit,
                   wind_speed, wind_direction, wind_unit,
                   raw_metadata, created_at
            FROM images
            WHERE {where_sql}
            ORDER BY {sort_by} {sort_order}
            LIMIT %s OFFSET %s
        """
        
        # Add pagination parameters
        params.extend([per_page, offset])
        
        # Execute the final query
        cur.execute(query, params)
        images = cur.fetchall()
        
        # Convert datetime objects to ISO format for JSON serialization
        for image in images:
            if image['capture_time']:
                image['capture_time'] = image['capture_time'].isoformat()
            if image['created_at']:
                image['created_at'] = image['created_at'].isoformat()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'images': images,
            'pagination': {
                'total': total_images,
                'page': page,
                'per_page': per_page,
                'total_pages': (total_images + per_page - 1) // per_page
            },
            'filters': {
                'start_date': start_date,
                'end_date': end_date,
                'location': location
            },
            'sorting': {
                'sort_by': sort_by,
                'sort_order': sort_order
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api.route('/images/<int:image_id>')
def get_image(image_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT id, reveal_id, cdn_url, capture_time,
                   primary_location, secondary_location,
                   temperature, temperature_unit,
                   wind_speed, wind_direction, wind_unit,
                   raw_metadata, created_at
            FROM images
            WHERE id = %s
        """, (image_id,))
        
        image = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if not image:
            return jsonify({'error': 'Image not found'}), 404
            
        # Convert datetime objects to ISO format
        if image['capture_time']:
            image['capture_time'] = image['capture_time'].isoformat()
        if image['created_at']:
            image['created_at'] = image['created_at'].isoformat()
        
        return jsonify(image)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Register the blueprint
app.register_blueprint(api)

@app.after_request
def add_headers(response):
    # Allow requests from Netlify frontend
    response.headers['Access-Control-Allow-Origin'] = os.getenv('FRONTEND_URL', '*')
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True) 
