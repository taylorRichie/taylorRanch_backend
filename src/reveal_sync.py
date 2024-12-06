import asyncio
from playwright.async_api import async_playwright # type: ignore
import os
from dotenv import load_dotenv # type: ignore
from datetime import datetime
import psycopg2 # type: ignore
from psycopg2.extras import Json # type: ignore
import hashlib
import boto3
from botocore.client import Config
import mimetypes
import uuid
from urllib.parse import urljoin

# Load environment variables from parent directory
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)

# Digital Ocean Spaces Configuration
spaces_client = boto3.client('s3',
    endpoint_url=f"https://{os.getenv('DO_SPACES_ENDPOINT')}",
    region_name=os.getenv('DO_SPACES_REGION', 'nyc3'),
    aws_access_key_id=os.getenv('DO_SPACES_KEY'),
    aws_secret_access_key=os.getenv('DO_SPACES_SECRET'),
    config=Config(signature_version='s3v4')
)

SPACE_NAME = os.getenv('DO_SPACE_NAME')
CDN_BASE_URL = os.getenv('CDN_BASE_URL')

# Constants
NAVIGATION_TIMEOUT = 30000
PAGE_LOAD_TIMEOUT = 10000
ELEMENT_TIMEOUT = 5000
DOWNLOAD_TIMEOUT = 30000
MAX_UPLOAD_RETRIES = 3
RETRY_DELAY = 5  # seconds
ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png']
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB

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
            await self.take_screenshot("login_page")  # 01-login_page
            
            await self.page.wait_for_timeout(3000)
            
            print("Attempting to log in...")
            print("Filling email...")
            await self.page.fill('input[data-testid="login-email-input"]', os.getenv('REVEAL_EMAIL'))
            await self.page.fill('input[data-testid="login-password-input"]', os.getenv('REVEAL_PASSWORD'))
            await self.take_screenshot("credentials_filled")  # 02-credentials_filled
            
            print("Looking for Sign In button...")
            sign_in_button = await self.page.wait_for_selector('button:has-text("Sign In")', timeout=ELEMENT_TIMEOUT)
            if sign_in_button:
                print("Found Sign In button, clicking...")
                await sign_in_button.click()
                await self.take_screenshot("after_signin")  # 03-after_signin
                
                await self.page.wait_for_timeout(5000)
                
                print("Checking for rewards dialog...")
                try:
                    close_button = await self.page.wait_for_selector('button:has-text("CLOSE")', timeout=5000)
                    if close_button:
                        print("Found rewards dialog, closing...")
                        await close_button.click()
                        await self.page.wait_for_timeout(2000)
                        await self.take_screenshot("after_dialog_close")  # 04-after_dialog_close
                except Exception as dialog_error:
                    print("No rewards dialog found or already closed")
                
            else:
                print("Could not find Sign In button")
                await self.take_screenshot("no_signin_button")
                raise Exception("Could not find Sign In button")
            
            print("Waiting for page to load after login...")
            await self.page.wait_for_timeout(PAGE_LOAD_TIMEOUT)
            await self.take_screenshot("main_gallery")  # 05-main_gallery
            print(f"Current URL: {self.page.url}")
            
        except Exception as e:
            print(f"Login error: {str(e)}")
            await self.page.screenshot(path="../logs/login_error.png")
            raise

    async def process_image(self, card=None):
        """Process a single image card or current detail view"""
        try:
            print("\nProcessing new image...")
            
            if card:
                # Initial card click case
                reveal_id = await card.get_attribute('id')
                if not reveal_id:
                    print("Could not get reveal_id, skipping...")
                    return
                    
                print(f"Processing card ID: {reveal_id}")
                await self.take_screenshot(f"before_click_{reveal_id}")

                # Click the card to open detailed view
                try:
                    await card.click()
                    print("Clicked image card")
                    await self.page.wait_for_selector('div[data-testid="PhotoSideBar-container"]', timeout=ELEMENT_TIMEOUT)
                    await self.page.wait_for_timeout(2000)
                    await self.take_screenshot("image_detail_view")
                except Exception as e:
                    print(f"Error clicking card or waiting for sidebar: {e}")
                    return
            else:
                # Arrow navigation case - get reveal_id from current detail view
                try:
                    # Wait for the detail view to be fully loaded
                    await self.page.wait_for_selector('div[data-testid="PhotoSideBar-container"]', timeout=ELEMENT_TIMEOUT)
                    
                    # Get the image element by ID
                    detail_image = await self.page.wait_for_selector('img#single-photo', timeout=ELEMENT_TIMEOUT)
                    if not detail_image:
                        print("Could not find detail view image")
                        return
                        
                    # Get the image source URL
                    src = await detail_image.get_attribute('src')
                    if not src:
                        print("Could not get image source URL")
                        return
                        
                    # Extract reveal_id from the URL
                    # URL format: .../864049054168226-100-4-12052024182210-V-W1018634.JPG?...
                    try:
                        # Get the filename part before the query parameters
                        filename = src.split('?')[0].split('/')[-1]
                        # Get the first part before any extension
                        reveal_id = filename.split('.')[0]
                        print(f"Extracted reveal_id from image: {reveal_id}")
                    except Exception as e:
                        print(f"Could not extract reveal_id from URL: {e}")
                        return
                    
                    # Check if we've already processed this ID
                    if reveal_id in self.processed_ids:
                        print(f"Already processed {reveal_id}, skipping...")
                        # Still need to navigate to next image
                        await self.page.keyboard.press('ArrowRight')
                        await self.page.wait_for_timeout(2000)
                        return
                        
                except Exception as e:
                    print(f"Error getting reveal_id from detail view: {e}")
                    return

            # Add to processed IDs set
            self.processed_ids.add(reveal_id)

            # Extract metadata
            metadata = await self.extract_metadata()
            if metadata:
                print("Metadata extracted")
                await self.take_screenshot("metadata_captured")
            else:
                print("Failed to extract metadata")
                return

            # Download image
            image_path = await self.download_image(reveal_id)
            if image_path:
                print("Image downloaded successfully")
                await self.take_screenshot("after_download")
                
                # Store in database
                try:
                    await self.store_image_data(metadata, image_path, reveal_id)
                    print("Data stored in database")
                except Exception as e:
                    print(f"Error storing data: {e}")
                    return

            if not card:  # Only navigate if we're not processing the first card
                # Navigate to next image using right arrow key
                try:
                    await self.page.keyboard.press('ArrowRight')
                    print("Navigated to next image")
                    await self.page.wait_for_timeout(2000)  # Wait for transition
                    await self.take_screenshot("next_image")
                    
                    # Verify we're in a new detail view
                    await self.page.wait_for_selector('div[data-testid="PhotoSideBar-container"]', timeout=ELEMENT_TIMEOUT)
                except Exception as e:
                    print(f"Error navigating to next image: {e}")
                    raise  # Propagate error to stop processing if navigation fails
            
        except Exception as e:
            print(f"Error processing image: {e}")
            if reveal_id:
                await self.take_screenshot(f"error_processing_{reveal_id}")
            raise

    async def extract_metadata(self):
        """Extract weather and other metadata from detailed view"""
        try:
            print("Extracting metadata...")
            # Wait for the sidebar to be visible
            sidebar = await self.page.wait_for_selector('div[data-testid="PhotoSideBar-container"]', timeout=ELEMENT_TIMEOUT)
            if not sidebar:
                raise Exception("Sidebar not found")

            metadata = {}

            # Get timestamp from h6 element
            try:
                timestamp_element = await sidebar.query_selector('h6.text-s1')
                if timestamp_element:
                    metadata['timestamp'] = await timestamp_element.text_content()
                    print(f"Found timestamp: {metadata['timestamp']}")
            except Exception as e:
                print(f"Error getting timestamp: {e}")

            # Get location (FEEDERS and CABIN)
            try:
                location_elements = await sidebar.query_selector_all('p.text-overline.text-primary')
                if location_elements and len(location_elements) >= 2:
                    metadata['location'] = {
                        'primary': await location_elements[0].text_content(),
                        'secondary': await location_elements[1].text_content()
                    }
                    print(f"Found location: {metadata['location']}")
            except Exception as e:
                print(f"Error getting location: {e}")

            # Get weather data from the grid
            try:
                # Find the weather grid container
                weather_grid = await sidebar.query_selector('div[data-testid="WeatherInformationView-Button"]')
                if weather_grid:
                    # Find all weather data containers within the grid
                    # Use a simpler selector first, then filter by height attribute
                    weather_containers = await weather_grid.query_selector_all('div.flex')
                    
                    for container in weather_containers:
                        # Check if this is a weather container by looking for the label
                        label_elem = await container.query_selector('p.text-overline.text-white')
                        if not label_elem:
                            continue
                            
                        label = await label_elem.text_content()
                        print(f"Found label: {label}")
                        
                        # Get the value (in text-primary)
                        value_elem = await container.query_selector('p.text-overline.text-primary')
                        if not value_elem:
                            continue
                        
                        value = await value_elem.text_content()
                        print(f"Found {label}: {value}")
                        
                        # Parse based on the type of data
                        if 'TEMP' in label.upper():
                            parts = value.split('°')
                            metadata['temperature'] = {
                                'value': float(parts[0]),
                                'unit': parts[1].strip()
                            }
                        elif 'WIND' in label.upper():
                            parts = value.split()
                            metadata['wind'] = {
                                'direction': parts[0],
                                'speed': float(parts[1]),
                                'unit': ' '.join(parts[2:])
                            }
                        elif 'PRESSURE' in label.upper():
                            parts = value.split()
                            metadata['pressure'] = {
                                'value': float(parts[0]),
                                'unit': parts[1]
                            }
                        elif 'SUN' in label.upper():
                            metadata['sun_status'] = value
                        elif 'MOON' in label.upper():
                            metadata['moon_phase'] = value.replace('\n', ' ')

            except Exception as e:
                print(f"Error getting weather data: {e}")
                print(f"Full error details: {str(e)}")

            print("Final metadata:", metadata)
            return metadata

        except Exception as e:
            print(f"Error extracting metadata: {e}")
            await self.page.screenshot(path=f"../logs/metadata_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            return None

    async def download_image(self, reveal_id):
        """Download individual image"""
        try:
            print("Looking for download button...")
            download_button = await self.page.wait_for_selector('button#button-download_image', timeout=ELEMENT_TIMEOUT)
            
            if download_button:
                print("Found download button")
                
                # Set up download path
                download_path = os.path.join(os.path.dirname(__file__), '..', 'downloads')
                os.makedirs(download_path, exist_ok=True)
                
                # Use reveal_id in filename
                filename = f'reveal_image_{reveal_id}.jpg'
                
                # Handle the download
                async with self.page.expect_download() as download_info:
                    await download_button.click()
                    print("Waiting for download to start...")
                    download = await download_info.value
                    
                    # Save the file
                    downloaded_path = os.path.join(download_path, filename)
                    await download.save_as(downloaded_path)
                    
                    file_size = os.path.getsize(downloaded_path)
                    print(f"Download completed! File size: {file_size / (1024*1024):.2f} MB")
                    
                    # Validate after download
                    if await self.validate_image(downloaded_path, reveal_id):
                        return downloaded_path
                    else:
                        print("Image validation failed or duplicate found")
                        os.unlink(downloaded_path)
                        return None
            else:
                print("Could not find download button")
                return None
                
        except Exception as e:
            print(f"Error downloading image: {e}")
            return None

    async def upload_to_spaces(self, file_path, reveal_id):
        """Upload file to DO Spaces with retry logic"""
        try:
            # Validate image
            if not self.validate_image_file(file_path):
                return None

            # Generate unique filename
            file_extension = os.path.splitext(file_path)[1]
            unique_filename = f"{reveal_id}_{uuid.uuid4()}{file_extension}"
            space_path = f"images/{unique_filename}"

            # Get content type
            content_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
            
            # Attempt upload with retries
            for attempt in range(MAX_UPLOAD_RETRIES):
                try:
                    print(f"Upload attempt {attempt + 1} of {MAX_UPLOAD_RETRIES}")
                    with open(file_path, 'rb') as image_file:
                        spaces_client.upload_fileobj(
                            image_file,
                            SPACE_NAME,
                            space_path,
                            ExtraArgs={
                                'ACL': 'public-read',
                                'ContentType': content_type,
                                'CacheControl': 'max-age=31536000'  # 1 year cache
                            }
                        )
                    print(f"Upload successful: {space_path}")
                    return f"{CDN_BASE_URL}/{space_path}"
                except Exception as e:
                    print(f"Upload attempt {attempt + 1} failed: {e}")
                    if attempt < MAX_UPLOAD_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY)
                    else:
                        raise

        except Exception as e:
            print(f"Error uploading to Spaces: {e}")
            return None

    def validate_image_file(self, file_path):
        """Validate image file type and size"""
        try:
            if not os.path.exists(file_path):
                print(f"File does not exist: {file_path}")
                return False

            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > MAX_IMAGE_SIZE:
                print(f"File too large: {file_size / (1024*1024):.2f}MB (max {MAX_IMAGE_SIZE / (1024*1024)}MB)")
                return False

            # Check file type
            content_type = mimetypes.guess_type(file_path)[0]
            if content_type not in ALLOWED_IMAGE_TYPES:
                print(f"Invalid file type: {content_type}")
                return False

            return True

        except Exception as e:
            print(f"Error validating image file: {e}")
            return False

    async def store_image_data(self, metadata, image_path, reveal_id):
        """Store image data in database and upload to DO Spaces"""
        try:
            # Calculate hash before upload
            with open(image_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()

            # Check if image already exists
            cursor = self.db_conn.cursor()
            cursor.execute(
                "SELECT id, cdn_url FROM images WHERE file_hash = %s OR reveal_id = %s",
                (file_hash, reveal_id)
            )
            existing = cursor.fetchone()
            
            if existing:
                print(f"Image already exists (ID: {existing[0]}, CDN: {existing[1]})")
                return

            # Upload to DO Spaces
            cdn_url = await self.upload_to_spaces(image_path, reveal_id)
            if not cdn_url:
                raise Exception("Failed to upload image to Spaces")

            # Parse metadata
            timestamp_str = metadata.get('timestamp', '')
            try:
                capture_time = datetime.strptime(timestamp_str, "%B %d, %Y %I:%M %p")
            except ValueError:
                capture_time = datetime.now()

            location = metadata.get('location', {})
            temperature = metadata.get('temperature', {})
            wind = metadata.get('wind', {})

            # Insert into database
            cursor.execute("""
                INSERT INTO images (
                    reveal_id, file_hash, cdn_url, capture_time,
                    primary_location, secondary_location,
                    temperature, temperature_unit,
                    wind_speed, wind_direction, wind_unit,
                    raw_metadata, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, NOW(), NOW()
                )
                """,
                (
                    reveal_id, file_hash, cdn_url, capture_time,
                    location.get('primary', ''), location.get('secondary', ''),
                    temperature.get('value'), temperature.get('unit', 'F'),
                    wind.get('speed'), wind.get('direction', ''), wind.get('unit', 'mph'),
                    Json(metadata)
                )
            )
            
            self.db_conn.commit()
            print(f"Stored image data for {reveal_id} with CDN URL: {cdn_url}")

            # Clean up local file
            os.remove(image_path)
            print(f"Cleaned up local file: {image_path}")

        except Exception as e:
            print(f"Error storing image data: {e}")
            if self.db_conn:
                self.db_conn.rollback()
            raise
        finally:
            if 'cursor' in locals():
                cursor.close()

    async def validate_image(self, image_path, reveal_id):
        """Validate if an image needs to be processed based on hash and reveal_id"""
        try:
            if not os.path.exists(image_path):
                print(f"Image file does not exist: {image_path}")
                return False

            # Calculate hash of new image
            with open(image_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()

            cursor = self.db_conn.cursor()
            
            # Check if image exists by hash or reveal_id
            cursor.execute("""
                SELECT id, cdn_url 
                FROM images 
                WHERE file_hash = %s OR reveal_id = %s
            """, (file_hash, reveal_id))
            
            result = cursor.fetchone()
            
            if result:
                print(f"Image already exists in database (ID: {result[0]}, CDN URL: {result[1]})")
                return False
                
            return True

        except Exception as e:
            print(f"Error validating image: {e}")
            return False
        finally:
            if 'cursor' in locals():
                cursor.close()

    async def get_latest_image_id(self):
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT reveal_id FROM images ORDER BY created_at DESC LIMIT 1")
        result = cursor.fetchone()
        cursor.close()
        return result[0] if result else None

    async def sync(self, force_check=False):
        try:
            self.cleanup_directories()
            await self.connect_db()
            
            # Get the latest image_id from our database
            latest_id = await self.get_latest_image_id()
            print(f"Latest image ID in database: {latest_id}")
            
            async with async_playwright() as p:
                self.browser = await p.chromium.launch(headless=True)
                self.context = await self.browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
                )
                self.page = await self.context.new_page()

                await self.login()
                
                # Get all available cards
                cards = await self.page.query_selector_all('div[data-testid="PhotoRow-photo-card"]')
                if not cards:
                    print("No image cards found")
                    return
                    
                print(f"Found {len(cards)} total cards")
                
                target_count = 2  # Temporarily set to 2 for testing
                successful_count = 0
                max_attempts = 10  # Reduced for testing
                attempt = 0
                found_existing = False
                
                # Process first card
                first_card = cards[0]
                try:
                    # Get the current image ID before processing
                    current_id = await self.get_current_image_id()
                    print(f"Processing first image with ID: {current_id}")
                    
                    if not force_check and latest_id and current_id == latest_id:
                        print("No new images to process")
                        return
                        
                    await self.process_image(first_card)
                    successful_count += 1
                    print(f"Successfully processed {successful_count} of {target_count} images")
                except Exception as e:
                    print(f"Error processing first card: {e}")
                
                # Process remaining images until we hit target or find existing
                while successful_count < target_count and attempt < max_attempts and not found_existing:
                    attempt += 1
                    try:
                        print(f"\nProcessing image {successful_count + 1} of {target_count} (attempt {attempt})")
                        
                        # Get current image ID before processing
                        current_id = await self.get_current_image_id()
                        print(f"Current image ID: {current_id}")
                        
                        # If we hit an existing image and we're not force checking, stop
                        if not force_check and latest_id and current_id == latest_id:
                            print(f"Reached existing image {current_id}, stopping sync")
                            found_existing = True
                            break
                        
                        # Get current record count
                        cursor = self.db_conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM images")
                        current_count = cursor.fetchone()[0]
                        cursor.close()
                        
                        # Process next image
                        await self.process_image(None)
                        
                        # Check if we successfully added a new record
                        cursor = self.db_conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM images")
                        new_count = cursor.fetchone()[0]
                        cursor.close()
                        
                        if new_count > current_count:
                            successful_count += 1
                            print(f"Successfully processed {successful_count} of {target_count} images")
                        else:
                            print("No new record added, continuing to next image")
                            
                    except Exception as e:
                        print(f"Error processing image: {e}")
                        # Continue to next attempt
                
                if successful_count == target_count:
                    print(f"\nSuccessfully processed all {target_count} images")
                elif found_existing:
                    print(f"\nProcessed {successful_count} new images before finding existing content")
                else:
                    print(f"\nOnly processed {successful_count} images after {attempt} attempts")

        except Exception as e:
            print(f"Sync error: {e}")
            raise e
        finally:
            if self.browser:
                await self.browser.close()
            if self.db_conn:
                self.db_conn.close()

    async def get_current_image_id(self):
        """Get the current image ID from the detail view"""
        try:
            # Wait for the single-photo element
            single_photo = await self.page.wait_for_selector('#single-photo', timeout=5000)
            if single_photo:
                return await single_photo.get_attribute('data-photo-id')
        except Exception as e:
            print(f"Error getting current image ID: {e}")
        return None

async def main():
    syncer = RevealSync()
    await syncer.sync()

if __name__ == "__main__":
    asyncio.run(main()) 
