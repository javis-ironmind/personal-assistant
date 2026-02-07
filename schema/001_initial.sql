-- Migration 001: Initial schema for personal_tasks
-- Created: 2026-02-07

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS personal_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    description TEXT,
    
    -- Task classification
    type VARCHAR(20) CHECK (type IN ('timed', 'untimed', 'deadline', 'reminder', 'note')),
    priority VARCHAR(3) CHECK (priority IN ('P0', 'P1', 'P2', 'P3')),
    status VARCHAR(20) DEFAULT 'todo' CHECK (status IN ('todo', 'in_progress', 'done', 'cancelled')),
    
    -- Timing
    due_at TIMESTAMP WITH TIME ZONE,
    duration_minutes INTEGER,
    recurring_rule VARCHAR(50),
    
    -- Context
    context VARCHAR(50),
    source VARCHAR(20), -- 'whatsapp', 'email', 'tui', 'heartbeat'
    
    -- Google sync tracking
    google_event_id VARCHAR(255),
    google_task_id VARCHAR(255),
    last_synced_at TIMESTAMP WITH TIME ZONE,
    
    -- Linked resources
    linked_email_id VARCHAR(255),
    linked_doc_id VARCHAR(255),
    linked_sheet_id VARCHAR(255),
    linked_drive_path TEXT,
    
    -- Metadata
    notes JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_personal_tasks_status ON personal_tasks(status) WHERE status != 'done';
CREATE INDEX IF NOT EXISTS idx_personal_tasks_due_at ON personal_tasks(due_at) WHERE status != 'done';
CREATE INDEX IF NOT EXISTS idx_personal_tasks_priority ON personal_tasks(priority);
CREATE INDEX IF NOT EXISTS idx_personal_tasks_context ON personal_tasks(context);
CREATE INDEX IF NOT EXISTS idx_personal_tasks_google_event ON personal_tasks(google_event_id) WHERE google_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_personal_tasks_google_task ON personal_tasks(google_task_id) WHERE google_task_id IS NOT NULL;

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_personal_tasks_updated_at
    BEFORE UPDATE ON personal_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Migration tracking
CREATE TABLE IF NOT EXISTS personal_assistant_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

INSERT INTO personal_assistant_migrations (version) VALUES (1)
ON CONFLICT (version) DO NOTHING;
