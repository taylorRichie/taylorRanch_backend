import asyncio
from playwright.async_api import async_playwright # type: ignore
import os
from dotenv import load_dotenv # type: ignore
from datetime import datetime

# Load environment variables
load_dotenv()

# After the imports, add timeout constants
NAVIGATION_TIMEOUT = 30000  # 30 seconds
PAGE_LOAD_TIMEOUT = 10000   # 10 seconds
ELEMENT_TIMEOUT = 5000      # 5 seconds
DOWNLOAD_TIMEOUT = 30000    # 30 seconds

async def test_auth():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        # Create logs directory if it doesn't exist
        os.makedirs('../logs', exist_ok=True)
        
        print("Navigating to Reveal login page...")
        response = await page.goto('https://account.revealcellcam.com/login')
        print(f"Response status: {response.status}")
        await page.screenshot(path="../logs/01_initial_page.png")
        
        # Wait for initial page load
        await page.wait_for_timeout(3000)
        
        print("Attempting to log in...")
        try:
            # Login process
            print("Filling email...")
            await page.fill('input[data-testid="login-email-input"]', os.getenv('REVEAL_EMAIL'))
            await page.fill('input[data-testid="login-password-input"]', os.getenv('REVEAL_PASSWORD'))
            await page.screenshot(path="../logs/02_filled_login.png")
            
            print("Looking for Sign In button...")
            sign_in_button = await page.wait_for_selector('button:has-text("Sign In")', timeout=ELEMENT_TIMEOUT)
            if sign_in_button:
                print("Found Sign In button, clicking...")
                await sign_in_button.click()
                await page.screenshot(path="../logs/02b_after_signin_click.png")
                
                # Wait for initial page load after login
                await page.wait_for_timeout(5000)
                
                # Check for rewards dialog
                print("Checking for rewards dialog...")
                try:
                    close_button = await page.wait_for_selector('button:has-text("CLOSE")', timeout=5000)
                    if close_button:
                        print("Found rewards dialog, closing...")
                        await close_button.click()
                        await page.wait_for_timeout(2000)
                        await page.screenshot(path="../logs/02c_after_dialog_close.png")
                except Exception as dialog_error:
                    print("No rewards dialog found or already closed")
                
            else:
                print("Could not find Sign In button")
                await page.screenshot(path="../logs/02c_no_signin_button.png")
            
            # Wait for page to load after login
            print("Waiting for page to load after login...")
            await page.wait_for_timeout(10000)  # 10 seconds
            await page.screenshot(path="../logs/03_after_login.png")
            print(f"Current URL: {page.url}")
            
            # Try to find the photo card
            print("\nLooking for photo cards...")
            cards = await page.query_selector_all('div[data-testid="PhotoRow-photo-card"]')
            print(f"Found {len(cards)} photo cards")
            await page.screenshot(path="../logs/04_found_cards.png")
            
            if cards:
                print("Found at least one card, hovering over it...")
                # Hover over the first card to reveal checkbox
                await cards[0].hover()
                await page.wait_for_timeout(1000)  # Wait for hover effect
                await page.screenshot(path="../logs/04b_hover_card.png")
                
                # Look for and click the checkbox
                print("Looking for checkbox...")
                checkbox = await page.wait_for_selector('button[role="checkbox"]', timeout=5000)
                if checkbox:
                    print("Found checkbox, clicking...")
                    await checkbox.click()
                    await page.wait_for_timeout(1000)
                    await page.screenshot(path="../logs/05_after_checkbox_click.png")
                    
                    # Look for SELECT ALL
                    print("Looking for SELECT ALL...")
                    select_all = await page.wait_for_selector('p.text-cardTitle:has-text("select all")', timeout=5000)
                    if select_all:
                        print("Found SELECT ALL, clicking...")
                        await select_all.click()
                        await page.wait_for_timeout(2000)
                        await page.screenshot(path="../logs/06_after_select_all.png")
                        
                        # Look for DOWNLOAD IMAGE button
                        print("Looking for DOWNLOAD IMAGES button...")
                        download_button = await page.wait_for_selector('button[data-testid="SelectedPhotosActionBar-Download-button"]', timeout=5000)
                        if download_button:
                            print("Found download button, clicking...")
                            
                            # Set up download path and filename before starting download
                            download_path = os.path.join(os.path.dirname(__file__), '..', 'downloads')
                            os.makedirs(download_path, exist_ok=True)
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            filename = f'reveal_images_{timestamp}.zip'
                            
                            # Handle the download
                            async with page.expect_download() as download_info:
                                await download_button.click()
                                print("Waiting for download to start...")
                                download = await download_info.value
                                print(f"Download started - suggested filename: {download.suggested_filename}")
                                
                                # Wait for the download to complete
                                print("Download started, waiting for completion...")
                                await page.wait_for_timeout(DOWNLOAD_TIMEOUT)
                                
                                # Add file size check after download
                                downloaded_path = os.path.join(download_path, filename)
                                await download.save_as(downloaded_path)
                                file_size = os.path.getsize(downloaded_path)
                                print(f"Download completed! File size: {file_size / (1024*1024):.2f} MB")
                                
                            await page.screenshot(path="../logs/08_download_complete.png")
                        else:
                            print("Could not find download button")
                            await page.screenshot(path="../logs/error_no_download_button.png")
                else:
                    print("Could not find checkbox")
                    await page.screenshot(path="../logs/error_no_checkbox.png")
            else:
                print("No photo cards found")
                await page.screenshot(path="../logs/error_no_cards.png")
            
        except Exception as e:
            print(f"\nError: {str(e)}")
            await page.screenshot(path="../logs/error_state.png")
            
            # Print current page state
            content = await page.content()
            print(f"\nPage content at error:")
            print(content[:1000])
            
        finally:
            await browser.close()

# Run the test
asyncio.run(test_auth())