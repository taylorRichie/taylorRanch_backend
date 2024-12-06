-- Drop existing tables if they exist
DROP TABLE IF EXISTS images CASCADE;

-- Create images table with new schema
CREATE TABLE images (
    id SERIAL PRIMARY KEY,
    reveal_id VARCHAR(255) NOT NULL,
    cdn_url TEXT NOT NULL,
    capture_time TIMESTAMP NOT NULL,
    primary_location VARCHAR(255),
    secondary_location VARCHAR(255),
    temperature FLOAT,
    temperature_unit VARCHAR(10),
    wind_speed FLOAT,
    wind_direction VARCHAR(10),
    wind_unit VARCHAR(10),
    raw_metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_hash VARCHAR(32) UNIQUE NOT NULL
);

-- Create indexes for common queries
CREATE INDEX idx_images_capture_time ON images(capture_time);
CREATE INDEX idx_images_locations ON images(primary_location, secondary_location);
CREATE INDEX idx_images_reveal_id ON images(reveal_id);
CREATE INDEX idx_images_file_hash ON images(file_hash);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_images_updated_at
    BEFORE UPDATE ON images
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column(); 