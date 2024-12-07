#!/usr/bin/env python3
import os
import time
from datetime import datetime, timedelta
import glob

# Configuration
LOG_DIR = "/var/www/reveal_gallery/logs/cron"
MAX_AGE_DAYS = 7

def cleanup_old_logs():
    """Remove log files older than MAX_AGE_DAYS"""
    print(f"Starting log cleanup at {datetime.now()}")
    
    # Calculate cutoff time
    cutoff = time.time() - (MAX_AGE_DAYS * 86400)  # 86400 seconds per day
    
    # Get all log files
    log_pattern = os.path.join(LOG_DIR, "reveal_sync_*.log")
    log_files = glob.glob(log_pattern)
    
    removed = 0
    for log_file in log_files:
        try:
            # Check file age
            if os.path.getmtime(log_file) < cutoff:
                os.remove(log_file)
                removed += 1
                print(f"Removed old log: {os.path.basename(log_file)}")
        except Exception as e:
            print(f"Error processing {log_file}: {e}")
    
    print(f"Cleanup complete. Removed {removed} old log files.")

if __name__ == "__main__":
    cleanup_old_logs() 