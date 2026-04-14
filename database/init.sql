-- =============================================================================
-- Behavior Intelligence Engine – PostgreSQL initialisation script
-- =============================================================================
-- This script is executed automatically when the PostgreSQL container
-- starts for the first time.  SQLAlchemy's init_db() will create any
-- tables not present, so this file primarily handles extensions and
-- performance indexes.
-- =============================================================================

-- Enable useful extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- text similarity
CREATE EXTENSION IF NOT EXISTS btree_gin; -- GIN indexes on scalar types

-- Ensure the schema is set up for the ORM (tables created by SQLAlchemy)
-- Nothing else to do here – init_db() in database/models.py handles DDL.
