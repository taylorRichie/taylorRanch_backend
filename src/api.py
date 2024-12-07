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

@app.route('/reveal_gallery/api/weather', methods=['GET'])
def get_weather_trends():
    try:
        # Get date range parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        interval = request.args.get('interval', 'hour')  # hour, day, or week
        
        # Validate interval
        if interval not in ['hour', 'day', 'week']:
            interval = 'hour'
            
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Build the query with date filtering and interval grouping
        query = """
            WITH intervals AS (
                SELECT
                    CASE
                        WHEN %s = 'hour' THEN date_trunc('hour', capture_time)
                        WHEN %s = 'day' THEN date_trunc('day', capture_time)
                        WHEN %s = 'week' THEN date_trunc('week', capture_time)
                    END as interval_start,
                    AVG(temperature) as avg_temp,
                    MIN(temperature) as min_temp,
                    MAX(temperature) as max_temp,
                    MODE() WITHIN GROUP (ORDER BY temperature_unit) as temp_unit,
                    AVG(wind_speed) as avg_wind,
                    MIN(wind_speed) as min_wind,
                    MAX(wind_speed) as max_wind,
                    MODE() WITHIN GROUP (ORDER BY wind_unit) as wind_unit,
                    MODE() WITHIN GROUP (ORDER BY wind_direction) as common_wind_dir,
                    COUNT(*) as reading_count
                FROM images
                WHERE capture_time IS NOT NULL
        """
        params = [interval, interval, interval]
        
        # Add date range filters if provided
        if start_date:
            query += " AND capture_time >= %s"
            params.append(start_date)
        if end_date:
            query += " AND capture_time <= %s"
            params.append(end_date)
            
        query += """
                GROUP BY interval_start
                ORDER BY interval_start DESC
            )
            SELECT * FROM intervals
        """
        
        cur.execute(query, params)
        readings = cur.fetchall()
        cur.close()
        conn.close()

        weather_data = []
        for reading in readings:
            weather_data.append({
                'timestamp': reading[0].isoformat(),
                'temperature': {
                    'average': round(reading[1], 1) if reading[1] else None,
                    'min': round(reading[2], 1) if reading[2] else None,
                    'max': round(reading[3], 1) if reading[3] else None,
                    'unit': reading[4]
                },
                'wind': {
                    'average': round(reading[5], 1) if reading[5] else None,
                    'min': round(reading[6], 1) if reading[6] else None,
                    'max': round(reading[7], 1) if reading[7] else None,
                    'unit': reading[8],
                    'common_direction': reading[9]
                },
                'reading_count': reading[10]
            })

        response = {
            'weather_data': weather_data,
            'metadata': {
                'interval': interval,
                'start_date': start_date,
                'end_date': end_date,
                'total_intervals': len(weather_data)
            }
        }

        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/reveal_gallery/api/weather/records', methods=['GET'])
def get_weather_records():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get coldest day
        coldest_query = """
            WITH daily_temps AS (
                SELECT 
                    date_trunc('day', capture_time) as day,
                    MIN(temperature) as min_temp,
                    MAX(temperature) as max_temp,
                    AVG(temperature) as avg_temp,
                    MODE() WITHIN GROUP (ORDER BY temperature_unit) as temp_unit,
                    MIN(wind_speed) as min_wind,
                    MAX(wind_speed) as max_wind,
                    AVG(wind_speed) as avg_wind,
                    MODE() WITHIN GROUP (ORDER BY wind_unit) as wind_unit,
                    MODE() WITHIN GROUP (ORDER BY wind_direction) as common_wind_dir
                FROM images
                WHERE temperature IS NOT NULL
                GROUP BY date_trunc('day', capture_time)
            ),
            coldest_day AS (
                SELECT day
                FROM daily_temps
                WHERE avg_temp = (SELECT MIN(avg_temp) FROM daily_temps)
                LIMIT 1
            )
            SELECT 
                dt.day,
                dt.min_temp, dt.max_temp, dt.avg_temp, dt.temp_unit,
                dt.min_wind, dt.max_wind, dt.avg_wind, dt.wind_unit, dt.common_wind_dir,
                json_agg(json_build_object(
                    'id', i.id,
                    'cdn_url', i.cdn_url,
                    'capture_time', to_char(i.capture_time, 'YYYY-MM-DD"T"HH24:MI:SS')
                ) ORDER BY i.capture_time) as images
            FROM daily_temps dt
            JOIN coldest_day cd ON dt.day = cd.day
            JOIN images i ON date_trunc('day', i.capture_time) = dt.day
            GROUP BY dt.day, dt.min_temp, dt.max_temp, dt.avg_temp, dt.temp_unit,
                     dt.min_wind, dt.max_wind, dt.avg_wind, dt.wind_unit, dt.common_wind_dir
        """
        
        # Get hottest day
        hottest_query = """
            WITH daily_temps AS (
                SELECT 
                    date_trunc('day', capture_time) as day,
                    MIN(temperature) as min_temp,
                    MAX(temperature) as max_temp,
                    AVG(temperature) as avg_temp,
                    MODE() WITHIN GROUP (ORDER BY temperature_unit) as temp_unit,
                    MIN(wind_speed) as min_wind,
                    MAX(wind_speed) as max_wind,
                    AVG(wind_speed) as avg_wind,
                    MODE() WITHIN GROUP (ORDER BY wind_unit) as wind_unit,
                    MODE() WITHIN GROUP (ORDER BY wind_direction) as common_wind_dir
                FROM images
                WHERE temperature IS NOT NULL
                GROUP BY date_trunc('day', capture_time)
            ),
            hottest_day AS (
                SELECT day
                FROM daily_temps
                WHERE avg_temp = (SELECT MAX(avg_temp) FROM daily_temps)
                LIMIT 1
            )
            SELECT 
                dt.day,
                dt.min_temp, dt.max_temp, dt.avg_temp, dt.temp_unit,
                dt.min_wind, dt.max_wind, dt.avg_wind, dt.wind_unit, dt.common_wind_dir,
                json_agg(json_build_object(
                    'id', i.id,
                    'cdn_url', i.cdn_url,
                    'capture_time', to_char(i.capture_time, 'YYYY-MM-DD"T"HH24:MI:SS')
                ) ORDER BY i.capture_time) as images
            FROM daily_temps dt
            JOIN hottest_day hd ON dt.day = hd.day
            JOIN images i ON date_trunc('day', i.capture_time) = dt.day
            GROUP BY dt.day, dt.min_temp, dt.max_temp, dt.avg_temp, dt.temp_unit,
                     dt.min_wind, dt.max_wind, dt.avg_wind, dt.wind_unit, dt.common_wind_dir
        """
        
        # Get windiest day
        windiest_query = """
            WITH daily_winds AS (
                SELECT 
                    date_trunc('day', capture_time) as day,
                    MIN(temperature) as min_temp,
                    MAX(temperature) as max_temp,
                    AVG(temperature) as avg_temp,
                    MODE() WITHIN GROUP (ORDER BY temperature_unit) as temp_unit,
                    MIN(wind_speed) as min_wind,
                    MAX(wind_speed) as max_wind,
                    AVG(wind_speed) as avg_wind,
                    MODE() WITHIN GROUP (ORDER BY wind_unit) as wind_unit,
                    MODE() WITHIN GROUP (ORDER BY wind_direction) as common_wind_dir
                FROM images
                WHERE wind_speed IS NOT NULL
                GROUP BY date_trunc('day', capture_time)
            ),
            windiest_day AS (
                SELECT day
                FROM daily_winds
                WHERE avg_wind = (SELECT MAX(avg_wind) FROM daily_winds)
                LIMIT 1
            )
            SELECT 
                dw.day,
                dw.min_temp, dw.max_temp, dw.avg_temp, dw.temp_unit,
                dw.min_wind, dw.max_wind, dw.avg_wind, dw.wind_unit, dw.common_wind_dir,
                json_agg(json_build_object(
                    'id', i.id,
                    'cdn_url', i.cdn_url,
                    'capture_time', to_char(i.capture_time, 'YYYY-MM-DD"T"HH24:MI:SS')
                ) ORDER BY i.capture_time) as images
            FROM daily_winds dw
            JOIN windiest_day wd ON dw.day = wd.day
            JOIN images i ON date_trunc('day', i.capture_time) = dw.day
            GROUP BY dw.day, dw.min_temp, dw.max_temp, dw.avg_temp, dw.temp_unit,
                     dw.min_wind, dw.max_wind, dw.avg_wind, dw.wind_unit, dw.common_wind_dir
        """
        
        # Execute queries
        cur.execute(coldest_query)
        coldest = cur.fetchone()
        
        cur.execute(hottest_query)
        hottest = cur.fetchone()
        
        cur.execute(windiest_query)
        windiest = cur.fetchone()
        
        cur.close()
        conn.close()
        
        def format_record(record):
            if not record:
                return None
                
            return {
                "timestamp": record[0].isoformat(),
                "temperature": {
                    "min": round(record[1], 1) if record[1] else None,
                    "max": round(record[2], 1) if record[2] else None,
                    "average": round(record[3], 1) if record[3] else None,
                    "unit": record[4]
                },
                "wind": {
                    "min": round(record[5], 1) if record[5] else None,
                    "max": round(record[6], 1) if record[6] else None,
                    "average": round(record[7], 1) if record[7] else None,
                    "unit": record[8],
                    "common_direction": record[9]
                },
                "images": [
                    {
                        "id": img["id"],
                        "cdn_url": img["cdn_url"],
                        "capture_time": img["capture_time"]
                    } for img in record[10]
                ]
            }
        
        response = {
            "coldest_day": format_record(coldest),
            "hottest_day": format_record(hottest),
            "windiest_day": format_record(windiest)
        }
        
        return jsonify(response)
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