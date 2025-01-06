#!/bin/bash

# Load environment variables
source /var/www/reveal_gallery/.env

# Set backup directory
BACKUP_DIR="/var/www/reveal_gallery/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SCHEMA_FILE="$BACKUP_DIR/reveal_gallery_schema_$TIMESTAMP.sql"
DATA_FILE="$BACKUP_DIR/reveal_gallery_data_$TIMESTAMP.sql"

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

# Backup schema
pg_dump -U $DB_USER -d $DB_NAME \
  --schema-only \
  --clean \
  --no-owner \
  --no-acl > $SCHEMA_FILE

# Backup data
pg_dump -U $DB_USER -d $DB_NAME \
  --data-only \
  --column-inserts \
  --no-owner \
  --no-acl > $DATA_FILE

# Compress the files
gzip $SCHEMA_FILE
gzip $DATA_FILE

# Keep only the last 7 backups of each type
ls -t $BACKUP_DIR/reveal_gallery_schema_*.sql.gz | tail -n +8 | xargs -r rm
ls -t $BACKUP_DIR/reveal_gallery_data_*.sql.gz | tail -n +8 | xargs -r rm

echo "Backup completed: ${SCHEMA_FILE}.gz and ${DATA_FILE}.gz" 