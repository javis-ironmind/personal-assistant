-- Migration 002: Webcal/iCal external calendar support
-- Created: 2026-02-07

-- Table to track external calendar sources
CREATE TABLE IF NOT EXISTS external_calendars (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,  -- User-friendly name (e.g., "Emmi School Calendar")
    url TEXT NOT NULL,           -- Webcal/ical URL
    calendar_type VARCHAR(20) DEFAULT 'webcal',  -- webcal, ical, google_ical, etc.
    
    -- Sync settings
    sync_enabled BOOLEAN DEFAULT true,
    sync_frequency VARCHAR(20) DEFAULT 'daily',  -- daily, hourly
    last_synced_at TIMESTAMP WITH TIME ZONE,
    last_sync_status VARCHAR(20),  -- success, error, pending
    last_sync_error TEXT,
    
    -- Filtering options
    default_context VARCHAR(50),   -- Auto-assign this context to imported events
    default_priority VARCHAR(3),   -- Auto-assign this priority
    title_filter VARCHAR(255),     -- Only import events matching this pattern (optional)
    
    -- Metadata
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for sync queries
CREATE INDEX IF NOT EXISTS idx_external_calendars_sync ON external_calendars(sync_enabled) WHERE sync_enabled = true;

-- Table to track synced events (for deduplication)
CREATE TABLE IF NOT EXISTS external_calendar_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_calendar_id UUID REFERENCES external_calendars(id) ON DELETE CASCADE,
    personal_task_id UUID REFERENCES personal_tasks(id) ON DELETE SET NULL,
    
    -- iCal fields
    ical_uid VARCHAR(255) NOT NULL,  -- Unique ID from iCal feed
    ical_sequence INTEGER,           -- Sequence number for updates
    ical_hash VARCHAR(64),           -- Hash of event content for change detection
    
    -- Sync tracking
    first_synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    sync_status VARCHAR(20) DEFAULT 'active',  -- active, updated, deleted
    
    UNIQUE(external_calendar_id, ical_uid)
);

-- Indexes for deduplication
CREATE INDEX IF NOT EXISTS idx_external_events_uid ON external_calendar_events(external_calendar_id, ical_uid);
CREATE INDEX IF NOT EXISTS idx_external_events_task ON external_calendar_events(personal_task_id);

-- Migration tracking
INSERT INTO personal_assistant_migrations (version) VALUES (2)
ON CONFLICT (version) DO NOTHING;
