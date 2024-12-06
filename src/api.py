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
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, reveal_id, cdn_url, capture_time, primary_location, secondary_location,
                   temperature, temperature_unit, wind_speed, wind_direction, wind_unit,
                   raw_metadata, created_at 
            FROM images 
            ORDER BY created_at DESC
        """)
        images = cur.fetchall()
        cur.close()
        conn.close()

        image_list = []
        for img in images:
            image_list.append({
                'id': img[0],
                'reveal_id': img[1],
                'cdn_url': img[2],
                'capture_time': img[3].isoformat() if img[3] else None,
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

        return jsonify({'images': image_list})
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