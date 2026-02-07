# personal-assistant

A personal task and time management system with natural language input, PostgreSQL storage, and one-way sync to Google Workspace.

---

## Overview

**Purpose:** Capture tasks, reminders, and events via chat (WhatsApp/TUI/Email), store in PostgreSQL, display in Google Calendar and Tasks.

**Philosophy:** I am the interface. No buttons, no timers, no confirmation flows. You speak, I act.

**Architecture:**
```
Input (WhatsApp/TUI/Email) → Me → PostgreSQL → Google Calendar/Tasks (view only)
```

---

## Core Features

### 1. Natural Language Input

Parse free-form messages into structured tasks:

| Input | Parsed |
|-------|--------|
| "Meeting with Sarah tomorrow 2pm for 30 min" | type=timed, due_at=tomorrow 14:00, duration=30 |
| "Remind me to call mom Friday" | type=untimed, due_at=Friday |
| "P0 finish taxes by April 1" | priority=P0, type=deadline, due_at=2026-04-01 |
| "Daily standup 9am recurring" | recurring_rule=daily, due_at=09:00 |
| "Note: idea for startup" | type=note, no calendar sync |

### 2. Storage (PostgreSQL)

**Table: `personal_tasks`**
```sql
CREATE TABLE personal_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    
    -- Task classification
    type VARCHAR(20) CHECK (type IN ('timed', 'untimed', 'deadline', 'reminder', 'note')),
    priority VARCHAR(3) CHECK (priority IN ('P0', 'P1', 'P2', 'P3')),
    status VARCHAR(20) DEFAULT 'todo' CHECK (status IN ('todo', 'in_progress', 'done', 'cancelled')),
    
    -- Timing
    due_at TIMESTAMP WITH TIME ZONE,
    duration_minutes INTEGER,
    recurring_rule VARCHAR(50), -- 'daily', 'weekly:mon', 'monthly:15'
    
    -- Context
    context VARCHAR(50), -- 'work', 'personal', 'health', 'finance', etc.
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

-- Indexes for common queries
CREATE INDEX idx_personal_tasks_status ON personal_tasks(status) WHERE status != 'done';
CREATE INDEX idx_personal_tasks_due_at ON personal_tasks(due_at) WHERE status != 'done';
CREATE INDEX idx_personal_tasks_priority ON personal_tasks(priority);
CREATE INDEX idx_personal_tasks_context ON personal_tasks(context);
```

### 3. One-Way Sync to Google

**Rules:**
- `type=timed` → Google Calendar (event with start/end time)
- `type=deadline` → Google Calendar (all-day event on due date) + Google Tasks
- `type=untimed|reminder` → Google Tasks only
- `type=note` → No Google sync (create Drive Doc optionally)

**Sync behavior:**
- Create: Insert to DB → sync to Google → store Google IDs
- Update: Modify DB → update Google (if IDs exist)
- Delete: Soft delete DB → delete from Google
- No two-way: Changes in Google Calendar/Tasks do NOT sync back

### 4. Daily Morning Report (6am Pacific)

**Format:**
```
Good morning. Today (Monday, Feb 7):

📅 TIMED ITEMS (3)
├── 09:00-09:30 Team standup
├── 14:00-15:00 Call with investor  
└── 17:00 ⏰ Submit proposal (DEADLINE)

📝 TASKS (5)
├── [P0] Review contract terms
├── [P1] Email follow-up: 3 pending replies
├── [P1] Draft Q1 roadmap
├── [P2] Book flight to Taiwan
└── [P2] Read article

📎 LINKED
├── Email: "Re: Proposal" (unread)
└── Doc: "Q1 Roadmap Draft"

Reply with: done <n> | add <task> | what about <query>
```

### 5. Interactive Queries

| You say | I respond |
|---------|-----------|
| "What do I have today?" | List today's timed items + tasks |
| "What's overdue?" | Items past due_at with status != done |
| "Done this week?" | Completed items since Monday |
| "What about project X?" | Tasks with context='project-x' or title match |
| "P0 items?" | All P0 priority tasks |
| "When is the Sarah meeting?" | Search title, return due_at |

### 6. Batch Operations

| You say | Action |
|---------|--------|
| "Done 1, 3, 5" | Mark tasks #1, #3, #5 as done |
| "Cancel the standup" | Find matching task, mark cancelled |
| "Move Sarah meeting to 3pm" | Update due_at, resync Calendar |
| "Snooze taxes by 2 days" | Add 2 days to due_at, resync |

---

## File Structure

```
personal-assistant/
├── SKILL.md                    # This spec
├── README.md                   # User-facing quick start
├── schema/
│   └── 001_initial.sql         # Database migrations
├── src/
│   ├── __init__.py
│   ├── parser.py               # Natural language → structured task
│   ├── storage.py              # PostgreSQL CRUD operations
│   ├── sync.py                 # Google Calendar/Tasks sync
│   ├── report.py               # Daily morning report generator
│   └── queries.py              # Interactive query handlers
├── scripts/
│   ├── daily_report.py         # Cron entry point (6am)
│   └── sync_daemon.py          # Background sync (optional)
├── config/
│   └── example.env             # Environment variables template
├── tests/
│   └── test_parser.py          # Unit tests for parser
└── .gitignore
```

---

## Dependencies

- `psycopg2` or `asyncpg` (PostgreSQL)
- `google-auth`, `google-api-python-client` (Google Calendar API, Tasks API)
- `dateparser` (natural language dates)
- `python-dotenv` (config)

---

## Environment Variables

```bash
# Database (same as kanban backend)
PA_DB_HOST=localhost
PA_DB_PORT=5432
PA_DB_NAME=kanban
PA_DB_USER=kanban
PA_DB_PASSWORD=kanban_secret

# Google OAuth (same as gog)
GOOGLE_CLIENT_SECRET_PATH=/home/ubuntu/.openclaw/credentials/client_secret.json
GOOGLE_ACCOUNT=nivlek99@gmail.com

# OpenClaw integration
PA_AGENT_ID=main
PA_TIMEZONE=America/Los_Angeles
PA_REPORT_TIME=06:00

# Optional
PA_CONTEXTS=work,personal,health,finance,travel,family
```

---

## Usage Examples

### Via WhatsApp
```
You: Meeting with Sarah tomorrow 2pm for 30 min
Me: ✅ Added "Meeting with Sarah" tomorrow 2:00-2:30pm

You: P0 finish taxes by April 1
Me: ✅ Added [P0] "finish taxes" deadline April 1

You: What do I have today?
Me: [morning report]

You: Done 1, 3
Me: ✅ Marked "Team standup" and "Review contract" as done
```

### Via Email
Forward action item emails to a configured address with subject prefix `[TASK]`:
```
Subject: [TASK] P1 Follow up on proposal
Body: [original email thread]
→ I extract, add to DB, reply with confirmation
```

### Via TUI
```bash
pa add "Meeting tomorrow 9am"
pa list --today
pa done 3
pa report
```

---

## Future Enhancements (Phase 2)

- [ ] Smart email extraction (parse forwarded threads)
- [ ] Weekly review (Sunday summary)
- [ ] Time blocking suggestions (find gaps, propose focus time)
- [ ] Context-aware queries ("what did I agree to with Sarah?")
- [ ] Integration with kanban (promote task to project task)

---

## Success Metrics

- Task capture: < 5 seconds from thought to DB
- Daily report: Generated reliably at 6am
- Sync reliability: > 99% (failures logged, retried)
- Query response: < 2 seconds for common questions

---

**Status:** SPEC REVIEW PENDING

**Next Step:** User reviews, approves, then implementation begins.
