from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST', 'localhost')
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {str(e)}")
        raise e

@app.route('/reveal_gallery/api/images', methods=['GET'])
def get_images():
    try:
        # Check if specific IDs were requested
        ids_param = request.args.get('ids')
        if ids_param:
            # Parse comma-separated IDs
            try:
                ids = [int(id.strip()) for id in ids_param.split(',')]
            except ValueError:
                return jsonify({'error': 'Invalid ID format'}), 400
                
            # Build query for specific IDs
            query = """
                SELECT id, reveal_id, cdn_url, capture_time, primary_location, secondary_location,
                       temperature, temperature_unit, wind_speed, wind_direction, wind_unit,
                       raw_metadata, created_at 
                FROM images 
                WHERE id = ANY(%s)
                ORDER BY array_position(%s, id)
            """
            params = [ids, ids]  # Pass ids twice: once for WHERE, once for ORDER BY
            
        else:
            # Get sorting parameters
            sort_by = request.args.get('sort_by', 'capture_time')
            sort_order = request.args.get('sort_order', 'desc').upper()
            
            # Get date range parameters
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            # Validate sort parameters
            allowed_sort_fields = ['capture_time', 'created_at', 'temperature', 'primary_location']
            if sort_by not in allowed_sort_fields:
                sort_by = 'capture_time'
            if sort_order not in ['ASC', 'DESC']:
                sort_order = 'DESC'
                
            # Build the query with dynamic sorting and date filtering
            query = """
                SELECT id, reveal_id, cdn_url, capture_time, primary_location, secondary_location,
                       temperature, temperature_unit, wind_speed, wind_direction, wind_unit,
                       raw_metadata, created_at 
                FROM images 
                WHERE 1=1
            """
            params = []
            
            # Add date range filters if provided
            if start_date:
                query += " AND capture_time >= %s"
                params.append(start_date)
            if end_date:
                query += " AND capture_time <= %s"
                params.append(end_date)
                
            query += f" ORDER BY {sort_by} {sort_order}"

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        images = cur.fetchall()
        cur.close()
        conn.close()

        image_list = []
        for img in images:
            capture_time = img[3]
            image_list.append({
                'id': img[0],
                'reveal_id': img[1],
                'cdn_url': img[2],
                'capture_time': capture_time.isoformat() if capture_time else None,
                'capture_time_formatted': capture_time.strftime('%B %d, %I:%M %p') if capture_time else None,
                'primary_location': img[4],
                'secondary_location': img[5],
                'temperature': img[6],
                'temperature_unit': img[7],
                'wind_speed': img[8],
                'wind_direction': img[9],
                'wind_unit': img[10],
                'raw_metadata': img[11],
                'created_at': img[12].isoformat() if img[12] else None
            })

        # Build response
        response = {'images': image_list}
        
        # Include sorting info if not using IDs
        if not ids_param:
            response.update({
                'sorting': {
                    'sort_by': sort_by,
                    'sort_order': sort_order
                },
                'filtering': {
                    'start_date': start_date,
                    'end_date': end_date,
                    'total_records': len(image_list)
                }
            })

        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/reveal_gallery/api/locations', methods=['GET'])
def get_locations():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT primary_location, secondary_location
            FROM images
            WHERE primary_location IS NOT NULL
            ORDER BY primary_location, secondary_location
        """)
        locations = cur.fetchall()
        cur.close()
        conn.close()

        location_list = []
        for loc in locations:
            location_list.append({
                'primary': loc[0],
                'secondary': loc[1]
            })

        return jsonify(location_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('API_PORT', 8000))
    print(f"Starting API server on port {port}")
    print(f"Database connection details:")
    print(f"  Database: {os.getenv('DB_NAME')}")
    print(f"  User: {os.getenv('DB_USER')}")
    print(f"  Host: {os.getenv('DB_HOST')}")
    app.run(host='0.0.0.0', port=port) 