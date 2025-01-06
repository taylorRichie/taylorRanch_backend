import os
import json
import base64
import requests
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
import google.generativeai as genai
from PIL import Image
import io

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

def get_db_connection():
    """Create database connection"""
    return psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT')
    )

def get_untagged_images(limit=20):
    """Get images that have no tags"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT i.id, i.cdn_url 
            FROM images i
            LEFT JOIN image_tags it ON i.id = it.image_id
            WHERE it.image_id IS NULL
            ORDER BY i.created_at DESC 
            LIMIT %s
        """, (limit,))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

def download_image(url):
    """Download image from URL"""
    response = requests.get(url)
    return response.content

def analyze_image(image_data):
    """Send image to Gemini AI for analysis"""
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = """You are a computer vision expert specializing in wildlife identification. 
    Please analyze this image and count any animals present. Only include animals that you are at least 90% confident about identifying.
    Be conservative in your counts - if you're unsure, do not include it.
    
    CRITICAL RULES:
    1. NEVER identify any bears - there are NO BEARS in these images
    2. What looks like a bear is always a black livestock feeder
    3. The black object in the middle/top of images is ALWAYS a feeder, not an animal
    4. If you're not 100% certain it's not a bear, do not include it at all
    
    You must ONLY respond with a valid JSON object, nothing else.
    Use this exact format and ALWAYS use plural forms:
    {
        "total": <sum of all animals>,
        <plural_animal_name>: <count>    # Always use plurals: "Rabbits", "Deer", "Coyotes", "Birds"
    }
    
    Look for any animals, such as Rabbits, Deer, Birds, you will occasionally see Coyotes, If you're not confident it's a coyote, it's probably a blurry rabbit at night.
    Only include animals that are:
    1. Clearly visible in the image
    2. You are at least 90% confident in identifying
    3. Are actual wildlife (not feeders, decoys, statues, or equipment)
    
    Note: Count all deer, including bucks, under "Deer"."""
    
    try:
        # Convert image data to PIL Image
        image = Image.open(io.BytesIO(image_data))
        
        response = model.generate_content([prompt, image])
        response.resolve()
        
        # Clean up the response to ensure valid JSON
        text = response.text.strip()
        if text.startswith('```json'):
            text = text[7:-3]
        elif text.startswith('```'):
            text = text[3:-3]
        return text.strip()
        
    except Exception as e:
        print(f"Error generating content: {e}")
        return "{}"

def format_tags_from_analysis(analysis_json):
    """Convert analysis results to tags array"""
    try:
        results = json.loads(analysis_json) if isinstance(analysis_json, str) else analysis_json
        tags = []
        
        # Track counts for each animal type
        animal_counts = {}
        
        for animal, count in results.items():
            if animal.lower() == 'total':
                continue
                
            if isinstance(count, (int, float)) and count > 0:
                # Normalize animal name: lowercase and remove trailing 's'
                animal_name = animal.lower().rstrip('s')
                
                # Combine counts for same animal
                if animal_name in animal_counts:
                    animal_counts[animal_name] += count
                else:
                    animal_counts[animal_name] = count
        
        # Create tags from combined counts
        for animal_name, count in animal_counts.items():
            # Skip deer for special handling
            if animal_name in ['deer', 'buck']:
                continue
                
            # Add animal tag
            tags.append({
                "type": "animal",
                "name": animal_name,
                "count": count,
                "display": f"{animal_name.capitalize()} {count}"
            })
        
        # Handle deer count separately
        deer_count = animal_counts.get('deer', 0) + animal_counts.get('buck', 0)
        if deer_count > 0:
            tags.append({
                "type": "animal",
                "name": "deer",
                "count": deer_count,
                "display": f"Deer {deer_count}"
            })
        
        return tags
        
    except Exception as e:
        print(f"Error formatting tags: {e}")
        return []

def create_or_get_tag(tag_data):
    """Create a tag if it doesn't exist and return its ID"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Convert tag data to JSON string
        tag_json = json.dumps(tag_data)
        
        # Try to get existing tag first
        cur.execute("""
            SELECT id FROM tags 
            WHERE name = %s
        """, (tag_json,))
        
        result = cur.fetchone()
        if result:
            return result[0]
            
        # Create new tag if it doesn't exist
        cur.execute("""
            INSERT INTO tags (name)
            VALUES (%s)
            RETURNING id
        """, (tag_json,))
        
        conn.commit()
        return cur.fetchone()[0]
        
    except Exception as e:
        print(f"Error creating/getting tag: {e}")
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()

def update_image_tags(image_id, tags):
    """Update image tags using the image_tags junction table"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # First, remove existing tags for this image
        cur.execute("DELETE FROM image_tags WHERE image_id = %s", (image_id,))
        
        # Now add the new tags
        for tag in tags:
            tag_id = create_or_get_tag(tag)
            if tag_id is None:
                continue
                
            cur.execute("""
                INSERT INTO image_tags (image_id, tag_id)
                VALUES (%s, %s)
            """, (image_id, tag_id))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Error updating image tags: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

def get_specific_images(image_ids):
    """Get specific images by ID"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT id, cdn_url 
            FROM images 
            WHERE id = ANY(%s)
        """, (image_ids,))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

def main():
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--images':
        image_ids = [int(id) for id in sys.argv[2].split(',')]
        image_records = get_specific_images(image_ids)
    else:
        image_records = get_untagged_images(20)
    
    if not image_records:
        print("No untagged images found in database")
        return
    
    print(f"Found {len(image_records)} untagged images to analyze")
    
    processed = 0
    for image_record in image_records:
        try:
            print(f"\nProcessing image {processed + 1} of {len(image_records)}")
            print(f"Analyzing image: {image_record['cdn_url']}")
            
            # Download image with retry
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    image_data = download_image(image_record['cdn_url'])
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        print(f"Failed to download image after {max_retries} attempts: {str(e)}")
                        continue
                    print(f"Download attempt {attempt + 1} failed, retrying...")
            
            # Analyze with Gemini
            try:
                result_text = analyze_image(image_data)
                
                # Try to parse as JSON and update tags
                try:
                    animal_counts = json.loads(result_text)
                    print("\nAnalysis Results:")
                    for animal, count in animal_counts.items():
                        print(f"{animal}: {count}")
                    
                    # Format and update tags
                    tags = format_tags_from_analysis(animal_counts)
                    if tags:
                        success = update_image_tags(image_record['id'], tags)
                        if success:
                            print("Tags updated successfully:", tags)
                            processed += 1
                        else:
                            print("Failed to update tags")
                    
                except json.JSONDecodeError:
                    print("Raw Analysis Results:")
                    print(result_text)
            
            except Exception as e:
                print("Error processing image:", str(e))
                continue
                
        except Exception as e:
            print(f"Error processing record: {str(e)}")
            continue
            
    print(f"\nProcessing complete. Successfully processed {processed} of {len(image_records)} images.")

if __name__ == "__main__":
    main() 