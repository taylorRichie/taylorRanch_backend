from reveal_analyze import get_db_connection, download_image, analyze_image, format_tags_from_analysis, update_image_tags
from psycopg2.extras import RealDictCursor
import json

def get_all_images():
    """Get all images from the database"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT id, cdn_url 
            FROM images 
            ORDER BY created_at DESC
        """)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

def main():
    # Clear existing tags
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM image_tags")
        cur.execute("DELETE FROM tags")
        conn.commit()
    finally:
        cur.close()
        conn.close()
    
    # Get all images
    image_records = get_all_images()
    total = len(image_records)
    print(f"Found {total} images to analyze")
    
    processed = 0
    for image_record in image_records:
        try:
            print(f"\nProcessing image {processed + 1} of {total}")
            print(f"Analyzing image: {image_record['cdn_url']}")
            
            image_data = download_image(image_record['cdn_url'])
            result_text = analyze_image(image_data)
            
            try:
                animal_counts = json.loads(result_text)
                print("\nAnalysis Results:")
                for animal, count in animal_counts.items():
                    print(f"{animal}: {count}")
                
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
            print(f"Error processing image {image_record['id']}: {str(e)}")
            continue
    
    print(f"\nProcessing complete. Successfully processed {processed} of {total} images.")

if __name__ == "__main__":
    main() 