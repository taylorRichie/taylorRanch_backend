import asyncio
from playwright.async_api import async_playwright  # type: ignore
import os
from dotenv import load_dotenv  # type: ignore
from datetime import datetime
import psycopg2  # type: ignore
from psycopg2.extras import Json  # type: ignore
import hashlib

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)

# Constants
NAVIGATION_TIMEOUT = 30000
PAGE_LOAD_TIMEOUT = 10000
ELEMENT_TIMEOUT = 5000
DOWNLOAD_TIMEOUT = 30000
STATIC_IMAGES_PATH = os.path.join('static', 'images')  # Symlinked path

class RevealSync:
    def __init__(self):
        self.db_conn = None
        self.browser = None
        self.context = None
        self.page = None
        self.screenshot_counter = 1
        self.processed_ids = set()  # Track processed IDs in memory
    
    def cleanup_directories(self):
        """Clean up logs and downloads directories before starting"""
        for dir_name in ['logs', 'downloads']:
            dir_path = os.path.join(os.path.dirname(__file__), '..', dir_name)
            if os.path.exists(dir_path):
                for file in os.listdir(dir_path):
                    file_path = os.path.join(dir_path, file)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                    except Exception as e:
                        print(f"Error deleting {file_path}: {e}")
            os.makedirs(dir_path, exist_ok=True)

    async def take_screenshot(self, description):
        """Take a screenshot with sequential numbering"""
        filename = f"{self.screenshot_counter:02d}-{description}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        await self.page.screenshot(path=f"../logs/{filename}")
        self.screenshot_counter += 1
        return filename

    async def connect_db(self):
        """Initialize database connection"""
        try:
            self.db_conn = psycopg2.connect(
                dbname=os.getenv('DB_NAME'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                host=os.getenv('DB_HOST', 'localhost')
            )
            print("Database connected successfully")
        except Exception as e:
            print(f"Database connection failed: {e}")
            raise

    async def login(self):
        """Handle Reveal login process"""
        try:
            print("Navigating to Reveal login page...")
            response = await self.page.goto('https://account.revealcellcam.com/login')
            print(f"Response status: {response.status}")
            await self.take_screenshot("login_page")
            
            await self.page.wait_for_timeout(3000)

            # Add your login logic here
        except Exception as e:
            print(f"Login failed: {e}")
            raise

    async def process_image_metadata(self, metadata):
        """Process and save image metadata to the database"""
        try:
            image_filename = metadata['filename']
            relative_path = os.path.join(STATIC_IMAGES_PATH, image_filename)

            # Insert metadata into the database
            cursor = self.db_conn.cursor()
            cursor.execute(
                """
                INSERT INTO images (filename, reveal_timestamp, location, file_path, reveal_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    metadata['filename'],
                    metadata['reveal_timestamp'],
                    Json(metadata['location']),
                    relative_path,
                    metadata['reveal_id']
                ),
            )
            image_id = cursor.fetchone()[0]

            # Insert weather data
            cursor.execute(
                """
                INSERT INTO weather_data (image_id, temperature, temp_unit, wind_speed, wind_direction, pressure, pressure_unit, sun_status, moon_phase)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    image_id,
                    metadata['temperature']['value'],
                    metadata['temperature']['unit'],
                    metadata['wind']['speed'],
                    metadata['wind']['direction'],
                    metadata['pressure']['value'],
                    metadata['pressure']['unit'],
                    metadata['sun_status'],
                    metadata['moon_phase']
                ),
            )
            self.db_conn.commit()
            print(f"Metadata stored successfully for image ID: {image_id}")
        except Exception as e:
            print(f"Failed to process metadata: {e}")
            raise

# Main async function
async def main():
    sync = RevealSync()
    await sync.connect_db()
    # Add logic to initialize Playwright and start processing images

if __name__ == "__main__":
    asyncio.run(main())
