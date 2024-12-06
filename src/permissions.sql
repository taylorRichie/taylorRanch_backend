-- Create user if not exists
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'reveal_user') THEN
      CREATE USER reveal_user WITH PASSWORD '84403-Skyline';
   END IF;
END
$do$;

-- Grant permissions
GRANT CONNECT ON DATABASE reveal_gallery TO reveal_user;
GRANT USAGE ON SCHEMA public TO reveal_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO reveal_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO reveal_user;

-- Make sure future tables will grant the same permissions
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO reveal_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO reveal_user; 