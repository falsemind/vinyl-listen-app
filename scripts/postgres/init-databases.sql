SELECT 'CREATE DATABASE vinyl_dev'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'vinyl_dev')\gexec

SELECT 'CREATE DATABASE vinyl_collection'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'vinyl_collection')\gexec
