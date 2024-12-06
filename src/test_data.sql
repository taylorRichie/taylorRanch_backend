-- Insert test data
INSERT INTO images (
    reveal_id, cdn_url, capture_time,
    primary_location, secondary_location,
    temperature, temperature_unit,
    wind_speed, wind_direction, wind_unit,
    raw_metadata, file_hash
) VALUES 
(
    'test1',
    'https://example.com/test1.jpg',
    '2024-01-01 12:00:00',
    'North Trail',
    'Cabin',
    72.5,
    'F',
    5.2,
    'NW',
    'mph',
    '{"pressure": {"value": 30.1, "unit": "inHg"}, "sun_status": "Sunny", "moon_phase": "Full Moon"}',
    'abc123'
),
(
    'test2',
    'https://example.com/test2.jpg',
    '2024-01-02 14:30:00',
    'South Ridge',
    'Stream',
    68.0,
    'F',
    3.1,
    'SE',
    'mph',
    '{"pressure": {"value": 29.9, "unit": "inHg"}, "sun_status": "Partly Cloudy", "moon_phase": "Waning"}',
    'def456'
),
(
    'test3',
    'https://example.com/test3.jpg',
    '2024-01-03 09:15:00',
    'East Creek',
    'Waterfall',
    65.2,
    'F',
    7.8,
    'E',
    'mph',
    '{"pressure": {"value": 30.0, "unit": "inHg"}, "sun_status": "Cloudy", "moon_phase": "New Moon"}',
    'ghi789'
); 