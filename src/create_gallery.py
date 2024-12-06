import os
import zipfile
from datetime import datetime
from pathlib import Path
import shutil

def create_gallery():
    # Setup directories
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    downloads_dir = os.path.join(base_dir, 'downloads')
    images_dir = os.path.join(base_dir, 'images')
    gallery_dir = os.path.join(base_dir, 'gallery')
    
    # Create directories if they don't exist
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(gallery_dir, exist_ok=True)
    
    # Find the most recent zip file
    zip_files = [f for f in os.listdir(downloads_dir) if f.endswith('.zip')]
    if not zip_files:
        print("No zip files found in downloads directory")
        return
    
    latest_zip = max(zip_files, key=lambda x: os.path.getctime(os.path.join(downloads_dir, x)))
    zip_path = os.path.join(downloads_dir, latest_zip)
    
    # Extract images
    print(f"Extracting {latest_zip}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(images_dir)
    
    # Get all images
    image_files = []
    for ext in ['.jpg', '.jpeg', '.png', '.gif']:
        image_files.extend(Path(images_dir).glob(f'**/*{ext}'))
        image_files.extend(Path(images_dir).glob(f'**/*{ext.upper()}'))
    
    # Sort images by creation time (newest first)
    image_files.sort(key=lambda x: x.stat().st_ctime, reverse=True)
    
    # Create HTML
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Trail Camera Gallery</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background: #1a1a1a;
                color: #fff;
            }
            .gallery {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 20px;
                padding: 20px;
            }
            .image-card {
                background: #2a2a2a;
                padding: 10px;
                border-radius: 8px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            }
            .image-card img {
                width: 100%;
                height: auto;
                border-radius: 4px;
            }
            .image-info {
                margin-top: 10px;
                font-size: 0.9em;
                color: #ccc;
            }
            h1 {
                text-align: center;
                color: #97D700;
                margin-bottom: 30px;
            }
        </style>
    </head>
    <body>
        <h1>Trail Camera Gallery</h1>
        <div class="gallery">
    """
    
    # Add images to HTML
    for img_path in image_files:
        # Copy image to gallery directory
        dest_path = os.path.join(gallery_dir, img_path.name)
        shutil.copy2(img_path, dest_path)
        
        # Get image creation time
        timestamp = datetime.fromtimestamp(img_path.stat().st_ctime)
        date_str = timestamp.strftime('%B %d, %Y %I:%M %p')
        
        html_content += f"""
            <div class="image-card">
                <img src="{img_path.name}" alt="Trail camera image">
                <div class="image-info">
                    <div>{date_str}</div>
                    <div>{img_path.name}</div>
                </div>
            </div>
        """
    
    html_content += """
        </div>
    </body>
    </html>
    """
    
    # Write HTML file
    html_path = os.path.join(gallery_dir, 'index.html')
    with open(html_path, 'w') as f:
        f.write(html_content)
    
    print(f"Gallery created at {html_path}")
    print(f"Found {len(image_files)} images")

if __name__ == "__main__":
    create_gallery() 
