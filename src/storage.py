"""PostgreSQL storage layer for personal tasks."""

import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor


class TaskStorage:
    """CRUD operations for personal tasks in PostgreSQL."""
    
    def __init__(self, 
                 host: str = None,
                 port: int = None,
                 database: str = None,
                 user: str = None,
                 password: str = None):
        """Initialize with database connection params."""
        self.conn_params = {
            'host': host or os.getenv('PA_DB_HOST', 'localhost'),
            'port': port or int(os.getenv('PA_DB_PORT', 5432)),
            'database': database or os.getenv('PA_DB_NAME', 'kanban'),
            'user': user or os.getenv('PA_DB_USER', 'kanban'),
            'password': password or os.getenv('PA_DB_PASSWORD', 'kanban_secret')
        }
    
    @contextmanager
    def _get_cursor(self):
        """Get database cursor with proper cleanup."""
        conn = psycopg2.connect(**self.conn_params)
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def create_task(self, 
                    title: str,
                    task_type: str,
                    due_at: Optional[datetime] = None,
                    duration_minutes: Optional[int] = None,
                    priority: Optional[str] = None,
                    context: Optional[str] = None,
                    recurring_rule: Optional[str] = None,
                    description: Optional[str] = None,
                    source: str = 'whatsapp',
                    linked_email_id: Optional[str] = None,
                    notes: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a new task."""
        with self._get_cursor() as cur:
            cur.execute("""
                INSERT INTO personal_tasks 
                (title, type, due_at, duration_minutes, priority, context, 
                 recurring_rule, description, source, linked_email_id, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """, (title, task_type, due_at, duration_minutes, priority, context,
                  recurring_rule, description, source, linked_email_id, 
                  json.dumps(notes) if notes else '{}'))
            return dict(cur.fetchone())
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a single task by ID."""
        with self._get_cursor() as cur:
            cur.execute("""
                SELECT * FROM personal_tasks 
                WHERE id = %s AND status != 'cancelled'
            """, (task_id,))
            result = cur.fetchone()
            return dict(result) if result else None
    
    def update_task(self, 
                    task_id: str,
                    **updates) -> Optional[Dict[str, Any]]:
        """Update task fields."""
        allowed_fields = ['title', 'description', 'type', 'due_at', 'duration_minutes',
                         'priority', 'status', 'context', 'recurring_rule', 'notes',
                         'google_event_id', 'google_task_id', 'linked_email_id',
                         'linked_doc_id', 'linked_sheet_id', 'linked_drive_path']
        
        # Filter to allowed fields
        updates = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not updates:
            return None
        
        # Handle notes JSON
        if 'notes' in updates and isinstance(updates['notes'], dict):
            updates['notes'] = json.dumps(updates['notes'])
        
        # Build SET clause
        set_clause = ', '.join(f"{k} = %s" for k in updates.keys())
        values = list(updates.values()) + [task_id]
        
        with self._get_cursor() as cur:
            cur.execute(f"""
                UPDATE personal_tasks 
                SET {set_clause}
                WHERE id = %s AND status != 'cancelled'
                RETURNING *
            """, values)
            result = cur.fetchone()
            return dict(result) if result else None
    
    def complete_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Mark a task as completed."""
        with self._get_cursor() as cur:
            cur.execute("""
                UPDATE personal_tasks 
                SET status = 'done', completed_at = NOW()
                WHERE id = %s AND status != 'cancelled'
                RETURNING *
            """, (task_id,))
            result = cur.fetchone()
            return dict(result) if result else None
    
    def cancel_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Soft-delete a task by marking as cancelled."""
        with self._get_cursor() as cur:
            cur.execute("""
                UPDATE personal_tasks 
                SET status = 'cancelled'
                WHERE id = %s
                RETURNING *
            """, (task_id,))
            result = cur.fetchone()
            return dict(result) if result else None
    
    def list_tasks(self, 
                   status: Optional[str] = None,
                   due_before: Optional[datetime] = None,
                   due_after: Optional[datetime] = None,
                   priority: Optional[str] = None,
                   context: Optional[str] = None,
                   limit: int = 100) -> List[Dict[str, Any]]:
        """List tasks with filters."""
        conditions = ["status != 'cancelled'"]
        params = []
        
        if status:
            conditions.append("status = %s")
            params.append(status)
        if due_before:
            conditions.append("due_at <= %s")
            params.append(due_before)
        if due_after:
            conditions.append("due_at >= %s")
            params.append(due_after)
        if priority:
            conditions.append("priority = %s")
            params.append(priority)
        if context:
            conditions.append("context = %s")
            params.append(context)
        
        where_clause = " AND ".join(conditions)
        
        with self._get_cursor() as cur:
            cur.execute(f"""
                SELECT * FROM personal_tasks 
                WHERE {where_clause}
                ORDER BY 
                    CASE priority 
                        WHEN 'P0' THEN 1 
                        WHEN 'P1' THEN 2 
                        WHEN 'P2' THEN 3 
                        WHEN 'P3' THEN 4 
                        ELSE 5 
                    END,
                    due_at ASC NULLS LAST,
                    created_at ASC
                LIMIT %s
            """, params + [limit])
            return [dict(row) for row in cur.fetchall()]
    
    def get_today_tasks(self) -> List[Dict[str, Any]]:
        """Get tasks due today."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        
        with self._get_cursor() as cur:
            cur.execute("""
                SELECT * FROM personal_tasks 
                WHERE status != 'cancelled'
                AND status != 'done'
                AND due_at >= %s AND due_at < %s
                ORDER BY due_at ASC
            """, (today, tomorrow))
            return [dict(row) for row in cur.fetchall()]
    
    def get_overdue_tasks(self) -> List[Dict[str, Any]]:
        """Get overdue tasks."""
        now = datetime.now()
        
        with self._get_cursor() as cur:
            cur.execute("""
                SELECT * FROM personal_tasks 
                WHERE status != 'cancelled'
                AND status != 'done'
                AND due_at < %s
                ORDER BY due_at ASC
            """, (now,))
            return [dict(row) for row in cur.fetchall()]
    
    def get_tasks_needing_sync(self) -> List[Dict[str, Any]]:
        """Get tasks that need to be synced to Google."""
        with self._get_cursor() as cur:
            cur.execute("""
                SELECT * FROM personal_tasks 
                WHERE status != 'cancelled'
                AND type IN ('timed', 'deadline', 'untimed', 'reminder')
                AND (last_synced_at IS NULL OR updated_at > last_synced_at)
                ORDER BY created_at ASC
            """)
            return [dict(row) for row in cur.fetchall()]
    
    def mark_synced(self, task_id: str, 
                    google_event_id: Optional[str] = None,
                    google_task_id: Optional[str] = None):
        """Mark a task as synced with Google IDs."""
        with self._get_cursor() as cur:
            cur.execute("""
                UPDATE personal_tasks 
                SET last_synced_at = NOW(),
                    google_event_id = COALESCE(%s, google_event_id),
                    google_task_id = COALESCE(%s, google_task_id)
                WHERE id = %s
            """, (google_event_id, google_task_id, task_id))
    
    def get_weekly_completed(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get tasks completed this week."""
        if since is None:
            since = datetime.now() - timedelta(days=7)
        
        with self._get_cursor() as cur:
            cur.execute("""
                SELECT * FROM personal_tasks 
                WHERE status = 'done'
                AND completed_at >= %s
                ORDER BY completed_at DESC
            """, (since,))
            return [dict(row) for row in cur.fetchall()]


from datetime import timedelta
