#!/bin/bash
cd /var/www/reveal_gallery
source venv/bin/activate
cd src

# Run the sync and capture output
python3 reveal_sync.py > sync_output.txt 2>&1
sync_status=$?

# Debug output
echo "=== Sync Output ==="
cat sync_output.txt
echo "=================="

# If sync was successful
if [ $sync_status -eq 0 ]; then
    echo "Sync completed successfully"
    
    # Extract new image IDs from output
    new_images=$(grep "New image IDs:" sync_output.txt | cut -d':' -f2-)
    echo "Found image IDs: '$new_images'"
    
    if [ ! -z "$new_images" ]; then
        echo "Starting analysis of new images..."
        python3 reveal_analyze.py --images "$new_images"
    else
        echo "No new images to analyze"
        echo "Checking for any untagged images..."
        python3 analyze_untagged.py
    fi
else
    echo "Sync failed with status $sync_status"
fi 