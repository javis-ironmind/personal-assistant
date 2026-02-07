# Personal Assistant

Natural language task management with PostgreSQL storage and Google Workspace integration.

## Quick Start

```bash
# 1. Set up environment
cp config/example.env .env
# Edit .env with your settings

# 2. Run migrations
psql -f schema/001_initial.sql

# 3. Test
python -m src.parser "Meeting tomorrow 2pm"
```

## Usage

**WhatsApp:** Send natural language tasks
- "Meeting with Sarah tomorrow 2pm for 30 min"
- "P0 finish taxes by April 1"
- "What do I have today?"

**Daily Report:** Automatically sent at 6am Pacific

## Architecture

```
WhatsApp/Email/TUI → Parser → PostgreSQL → Google Calendar/Tasks
```

- **Source of truth:** PostgreSQL
- **View layer:** Google Calendar + Tasks (one-way sync)
- **Interface:** Me (natural language, immediate action)

## License

MIT
