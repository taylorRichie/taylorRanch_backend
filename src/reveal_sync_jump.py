#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import Json
import hashlib
import boto3
from botocore.client import Config
import mimetypes
import uuid
from urllib.parse import urljoin
import argparse
import time
from reveal_sync import RevealSync  # Import the original RevealSync class

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

class RevealSyncJump(RevealSync):
    def __init__(self, jump_count, record_limit):
        super().__init__()
        self.jump_count = jump_count
        self.record_limit = record_limit
    
    async def jump_to_position(self):
        """Jump forward by clicking right arrow key multiple times"""
        print(f"\nJumping forward {self.jump_count} images...")
        
        # Click first card to enter detail view
        cards = await self.page.query_selector_all('div[data-testid="PhotoRow-photo-card"]')
        if not cards:
            raise Exception("No image cards found")
            
        await cards[0].click()
        await self.page.wait_for_selector('div[data-testid="PhotoSideBar-container"]', timeout=ELEMENT_TIMEOUT)
        await self.page.wait_for_timeout(2000)
        
        # Jump forward
        for i in range(self.jump_count):
            try:
                await self.page.keyboard.press('ArrowRight')
                await self.page.wait_for_timeout(500)  # Small delay between jumps
                
                if (i + 1) % 10 == 0:  # Progress update every 10 jumps
                    print(f"Jumped forward {i + 1} of {self.jump_count}")
                    
            except Exception as e:
                print(f"Error during jump at position {i}: {e}")
                return False
        
        print("Jump complete")
        return True

    async def sync(self):
        """Main sync process with jump functionality"""
        try:
            print("\nStarting sync process...")
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
                
                # Perform the jump
                if not await self.jump_to_position():
                    print("Failed to jump to desired position")
                    return
                
                successful_count = 0
                max_attempts = 200
                attempt = 0
                
                # Process images after the jump
                while successful_count < self.record_limit and attempt < max_attempts:
                    attempt += 1
                    try:
                        print(f"\nProcessing image {successful_count + 1} of {self.record_limit} (attempt {attempt})")
                        
                        success, is_duplicate = await self.process_image(None)
                        
                        if success:
                            successful_count += 1
                            print(f"Successfully processed {successful_count} images")
                        
                    except Exception as e:
                        print(f"Error processing image: {e}")
                
                if successful_count == self.record_limit:
                    print(f"\nSuccessfully processed {self.record_limit} images")
                else:
                    print(f"\nProcessed {successful_count} images after {attempt} attempts")
                
        except Exception as e:
            print(f"Sync error: {e}")
            raise e
        finally:
            if self.browser:
                await self.browser.close()
            if self.db_conn:
                self.db_conn.close()

async def main():
    parser = argparse.ArgumentParser(description='Sync images from Reveal camera with jump functionality')
    parser.add_argument('--jump', type=int, required=True, help='Number of images to jump forward')
    parser.add_argument('--limit', type=int, required=True, help='Number of images to process after jumping')
    args = parser.parse_args()

    syncer = RevealSyncJump(args.jump, args.limit)
    print(f"Starting sync with jump={args.jump}, limit={args.limit}")
    await syncer.sync()

if __name__ == "__main__":
    asyncio.run(main()) 