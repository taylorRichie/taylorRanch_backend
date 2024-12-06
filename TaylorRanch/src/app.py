from flask import Flask, render_template, jsonify, url_for, Blueprint # type: ignore
import psycopg2 # type: ignore
from psycopg2.extras import RealDictCursor # type: ignore
import os
from dotenv import load_dotenv # type: ignore

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)

app = Flask(__name__, 
           static_url_path='/reveal_gallery/static', 
           static_folder='static')
app.config['APPLICATION_ROOT'] = '/reveal_gallery'

reveal = Blueprint('reveal', __name__, url_prefix='/reveal_gallery')

def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST', 'localhost')
    )

# Add URL prefix for all routes
@reveal.route('/')
def gallery():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get all images with their metadata
    cur.execute("""
        SELECT i.*, w.temperature, w.temperature_unit, 
               w.wind_speed, w.wind_direction,
               w.pressure, w.pressure_unit,
               w.sun_status, w.moon_phase
        FROM images i
        LEFT JOIN weather_data w ON w.image_id = i.id
        ORDER BY i.reveal_timestamp DESC
    """)
    images = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('gallery.html', images=images)

@reveal.route('/image/<int:image_id>')
def image_detail(image_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get image and weather data
    cur.execute("""
        SELECT i.*, w.temperature, w.temperature_unit, 
               w.wind_speed, w.wind_direction,
               w.pressure, w.pressure_unit,
               w.sun_status, w.moon_phase
        FROM images i
        LEFT JOIN weather_data w ON w.image_id = i.id
        WHERE i.id = %s
    """, (image_id,))
    image = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return render_template('detail.html', image=image)

@app.after_request
def add_security_headers(response):
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https:; "
        "font-src 'self'; "
        "object-src 'none'; "
        "media-src 'self'; "
        "frame-src 'self';"
    )
    return response

# Register the blueprint
app.register_blueprint(reveal)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000) 