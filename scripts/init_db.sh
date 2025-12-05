#!/bin/bash
# Initialize or reset the Flux database schema
set -e

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres}"
DB_NAME="${DB_NAME:-flux}"

echo "🔄 Initializing Flux database schema..."
echo "   Host: $DB_HOST:$DB_PORT"
echo "   Database: $DB_NAME"

# Apply schema
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f schema.sql

echo "✅ Database schema initialized successfully!"
echo ""
echo "Next steps:"
echo "  - Create a test user: uv run python scripts/create_test_user.py"
echo "  - Seed demo data: uv run python scripts/seed_demo_data.py"
