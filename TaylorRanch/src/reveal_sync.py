import asyncio
from playwright.async_api import async_playwright # type: ignore
import os
from dotenv import load_dotenv # type: ignore
from datetime import datetime
import psycopg2 # type: ignore
from psycopg2.extras import Json # type: ignore
import hashlib

# Load environment variables from parent directory
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)

# Constants
NAVIGATION_TIMEOUT = 30000
PAGE_LOAD_TIMEOUT = 10000
ELEMENT_TIMEOUT = 5000
DOWNLOAD_TIMEOUT = 30000

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

    async def process_image(self, card):
        """Process a single image card"""
        try:
            print("\nProcessing new image...")
            
            # Get card ID first
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

            # Return to gallery
            try:
                back_button = await self.page.wait_for_selector('div.flex.h-full.flex-col.truncate.text-ellipsis.pr-2', timeout=5000)
                if back_button:
                    await back_button.click()
                    print("Returned to gallery view")
                    await self.page.wait_for_timeout(2000)  # Increased wait time
                    await self.take_screenshot("back_to_gallery")
            except Exception as e:
                print(f"Error returning to gallery: {e}")
                await self.page.reload()
                await self.page.wait_for_timeout(PAGE_LOAD_TIMEOUT)
            
        except Exception as e:
            print(f"Error processing image: {e}")
            await self.take_screenshot(f"error_processing_{reveal_id}")

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

    async def store_image_data(self, metadata, image_path, reveal_id):
        cursor = None
        try:
            if not image_path:
                print("No image path provided, skipping database storage")
                return
                
            cursor = self.db_conn.cursor()
            cursor.execute("BEGIN")
            
            # Parse the reveal timestamp from metadata
            reveal_timestamp = datetime.now()  # Default to current time
            if metadata and 'timestamp' in metadata:
                try:
                    timestamp_str = metadata['timestamp'].strip()
                    print(f"Parsing timestamp: {timestamp_str}")
                    try:
                        reveal_timestamp = datetime.strptime(timestamp_str, '%B %d, %I:%M %p')
                    except ValueError:
                        try:
                            reveal_timestamp = datetime.strptime(timestamp_str, '%B %d, %I:%M %p %Y')
                        except ValueError:
                            print(f"Could not parse timestamp: {timestamp_str}, using current time")
                            
                    reveal_timestamp = reveal_timestamp.replace(year=datetime.now().year)
                    print(f"Parsed timestamp: {reveal_timestamp}")
                except Exception as e:
                    print(f"Error parsing timestamp: {e}")
            
            # Calculate file hash
            with open(image_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            file_size = os.path.getsize(image_path)
            
            # Insert into images table with reveal_id
            cursor.execute("""
                INSERT INTO images (
                    filename,
                    reveal_timestamp,
                    download_timestamp,
                    location,
                    file_path,
                    file_size,
                    is_new,
                    hash,
                    reveal_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                os.path.basename(image_path),
                reveal_timestamp,
                datetime.now(),
                metadata.get('location', {}).get('primary', '') if metadata else None,
                image_path,
                file_size,
                metadata.get('is_new', True) if metadata else True,
                file_hash,
                reveal_id  # Add reveal_id to the insert
            ))
            
            image_id = cursor.fetchone()[0]
            
            # Insert weather data if available
            if metadata and any(key in metadata for key in ['temperature', 'wind', 'pressure', 'sun_status', 'moon_phase']):
                print("Attempting to insert weather data...")
                try:
                    cursor.execute("""
                        INSERT INTO weather_data (
                            image_id,
                            temperature,
                            temperature_unit,
                            wind_speed,
                            wind_direction,
                            pressure,
                            pressure_unit,
                            sun_status,
                            moon_phase
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        image_id,
                        metadata['temperature']['value'] if 'temperature' in metadata else None,
                        metadata['temperature']['unit'] if 'temperature' in metadata else None,
                        metadata['wind']['speed'] if 'wind' in metadata else None,
                        metadata['wind']['direction'] if 'wind' in metadata else None,
                        metadata['pressure']['value'] if 'pressure' in metadata else None,
                        metadata['pressure']['unit'] if 'pressure' in metadata else None,
                        metadata['sun_status'] if 'sun_status' in metadata else None,
                        metadata['moon_phase'] if 'moon_phase' in metadata else None
                    ))
                    print(f"Successfully inserted weather data for image ID: {image_id}")
                except Exception as e:
                    print(f"Error inserting weather data: {e}")
                    raise
            
            self.db_conn.commit()
            print(f"Successfully stored image and metadata with ID: {image_id}")
            
        except Exception as e:
            print(f"Error storing data in database: {e}")
            self.db_conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()

    async def validate_image(self, image_path, reveal_id):
        """Validate image and check if already processed"""
        try:
            if not os.path.exists(image_path):
                print(f"Image file not found: {image_path}")
                return False
            
            file_size = os.path.getsize(image_path)
            print(f"Validating image: {image_path} (size: {file_size} bytes)")
            
            # Check if we've already processed this reveal_id in this session
            if reveal_id in self.processed_ids:
                print(f"Already processed reveal_id: {reveal_id} in this session")
                return False
                
            # Check if file size is reasonable
            if file_size < 1000:
                print(f"Image too small ({file_size} bytes)")
                return False
                
            # Check if reveal_id exists in database
            cursor = self.db_conn.cursor()
            try:
                cursor.execute("SELECT id, filename FROM images WHERE reveal_id = %s", (reveal_id,))
                existing = cursor.fetchone()
                
                if existing:
                    print(f"Image already exists in database - ID: {existing[0]}, Filename: {existing[1]}")
                    return False
                    
                # Add to processed IDs set
                self.processed_ids.add(reveal_id)
                print(f"Image validation passed: {image_path}")
                return True
                
            finally:
                cursor.close()
            
        except Exception as e:
            print(f"Error validating image: {e}")
            return False

    async def sync(self):
        try:
            self.cleanup_directories()
            await self.connect_db()
            
            async with async_playwright() as p:
                self.browser = await p.chromium.launch(headless=True)
                self.context = await self.browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
                )
                self.page = await self.context.new_page()

                await self.login()
                
                # Get initial list of cards
                cards = await self.page.query_selector_all('div[data-testid="PhotoRow-photo-card"]')
                print(f"Found {len(cards)} total cards")
                
                # Process up to max_images cards
                max_images = 2
                for i in range(min(len(cards), max_images)):
                    print(f"\nProcessing image {i + 1} of {max_images}")
                    
                    # Get fresh list of cards each time
                    cards = await self.page.query_selector_all('div[data-testid="PhotoRow-photo-card"]')
                    if i < len(cards):
                        card = cards[i]  # Get the i-th card instead of always cards[0]
                        reveal_id = await card.get_attribute('id')
                        print(f"Processing card ID: {reveal_id}")
                        
                        await self.process_image(card)
                        await self.page.wait_for_timeout(2000)
                    else:
                        print(f"No card found at index {i}")
                        break

                print("Finished processing images")

        except Exception as e:
            print(f"Sync error: {e}")
        finally:
            if self.browser:
                await self.browser.close()
            if self.db_conn:
                self.db_conn.close()

async def main():
    syncer = RevealSync()
    await syncer.sync()

if __name__ == "__main__":
    asyncio.run(main()) 
