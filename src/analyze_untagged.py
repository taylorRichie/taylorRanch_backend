import json
from reveal_analyze import (
    get_db_connection, 
    download_image, 
    analyze_image, 
    format_tags_from_analysis, 
    update_image_tags
)
from psycopg2.extras import RealDictCursor

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

def count_untagged_images():
    """Get total count of untagged images"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT COUNT(*) 
            FROM images i
            LEFT JOIN image_tags it ON i.id = it.image_id
            WHERE it.image_id IS NULL
        """)
        return cur.fetchone()[0]
    finally:
        cur.close()
        conn.close()

def main():
    # First check total untagged images
    total_untagged = count_untagged_images()
    if total_untagged == 0:
        print("No untagged images found in database")
        return
    
    print(f"Found {total_untagged} total untagged images")
    print(f"Processing next batch of up to 20 images...")
    
    # Get next batch of untagged images
    image_records = get_untagged_images(20)
    
    processed = 0
    for image_record in image_records:
        try:
            print(f"\nProcessing image {processed + 1} of {len(image_records)}")
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
    
    remaining = total_untagged - processed
    print(f"\nProcessing complete. Successfully processed {processed} of {len(image_records)} images.")
    print(f"Remaining untagged images: {remaining}")

if __name__ == "__main__":
    main() 