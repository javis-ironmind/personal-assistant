"""Daily morning report generator."""

from datetime import datetime, timedelta
from typing import List, Dict, Any
from storage import TaskStorage


class ReportGenerator:
    """Generate daily morning reports."""
    
    def __init__(self, storage: TaskStorage = None):
        """Initialize with storage."""
        self.storage = storage or TaskStorage()
    
    def generate_daily_report(self, target_date: datetime = None) -> str:
        """Generate formatted daily report."""
        if target_date is None:
            target_date = datetime.now()
        
        # Get tasks for today
        today_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        timed_items = self.storage.list_tasks(
            due_after=today_start,
            due_before=today_end,
            status='todo'
        )
        
        # Separate by type
        calendar_items = [t for t in timed_items if t['type'] == 'timed']
        deadlines = [t for t in timed_items if t['type'] == 'deadline']
        
        # Get all pending tasks
        all_pending = self.storage.list_tasks(status='todo', limit=50)
        untimed_tasks = [t for t in all_pending if t['type'] in ('untimed', 'reminder')]
        
        # Sort by priority
        def priority_sort(task):
            p = task.get('priority', 'P3')
            return {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}.get(p, 4)
        
        untimed_tasks.sort(key=priority_sort)
        
        # Get overdue tasks
        overdue = self.storage.get_overdue_tasks()
        
        # Format report
        lines = [
            f"Good morning. Today ({target_date.strftime('%A, %b %d')}):",
            ""
        ]
        
        # Timed items
        if calendar_items or deadlines:
            lines.append(f"📅 TIMED ITEMS ({len(calendar_items) + len(deadlines)})")
            for item in sorted(calendar_items, key=lambda x: x['due_at'] or ''):
                time_str = self._format_time(item['due_at'])
                duration = item.get('duration_minutes', 30)
                end_time = self._format_end_time(item['due_at'], duration)
                lines.append(f"├── {time_str}-{end_time} {item['title']}")
            
            for item in deadlines:
                lines.append(f"└── ⏰ {item['title']} (DEADLINE)")
            lines.append("")
        
        # Overdue items
        if overdue:
            lines.append(f"🔴 OVERDUE ({len(overdue)})")
            for item in overdue[:5]:  # Show max 5
                due_str = self._format_date(item['due_at'])
                p = item.get('priority', '')
                p_str = f"[{p}] " if p else ""
                lines.append(f"├── {p_str}{item['title']} (due {due_str})")
            if len(overdue) > 5:
                lines.append(f"└── ... and {len(overdue) - 5} more")
            lines.append("")
        
        # Untimed tasks
        if untimed_tasks:
            lines.append(f"📝 TASKS ({len(untimed_tasks)})")
            for i, item in enumerate(untimed_tasks[:10], 1):
                p = item.get('priority', '')
                p_str = f"[{p}] " if p else ""
                lines.append(f"├── {i}. {p_str}{item['title']}")
            if len(untimed_tasks) > 10:
                lines.append(f"└── ... and {len(untimed_tasks) - 10} more")
            lines.append("")
        
        # Linked items section (placeholder - would integrate with Gmail/Drive)
        # lines.append("📎 LINKED")
        # lines.append("└── (Email and document integration coming soon)")
        # lines.append("")
        
        # Closing
        if not (calendar_items or deadlines or untimed_tasks):
            lines.append("✨ Nothing scheduled today. Enjoy the free time!")
        else:
            lines.append("Reply with: done <n> | add <task> | snooze <id> <duration>")
        
        return "\n".join(lines)
    
    def generate_weekly_summary(self) -> str:
        """Generate weekly summary report."""
        completed = self.storage.get_weekly_completed()
        pending = self.storage.list_tasks(status='todo', limit=100)
        overdue = self.storage.get_overdue_tasks()
        
        lines = [
            "📊 Weekly Summary",
            "",
            f"✅ Completed: {len(completed)} tasks",
            f"⏳ Pending: {len(pending)} tasks",
            f"🔴 Overdue: {len(overdue)} tasks",
            ""
        ]
        
        if completed:
            lines.append("Recent completions:")
            for item in completed[:5]:
                lines.append(f"  • {item['title']}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_time(self, dt) -> str:
        """Format datetime as HH:MM."""
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        return dt.strftime('%H:%M') if dt else '??:??'
    
    def _format_end_time(self, start_dt, duration_minutes: int) -> str:
        """Calculate and format end time."""
        if isinstance(start_dt, str):
            start_dt = datetime.fromisoformat(start_dt.replace('Z', '+00:00'))
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        return end_dt.strftime('%H:%M')
    
    def _format_date(self, dt) -> str:
        """Format datetime as relative date."""
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        delta = now - dt
        
        if delta.days == 0:
            return "today"
        elif delta.days == 1:
            return "yesterday"
        elif delta.days < 7:
            return f"{delta.days} days ago"
        else:
            return dt.strftime('%b %d')


if __name__ == "__main__":
    # Test report generation
    gen = ReportGenerator()
    print(gen.generate_daily_report())
    print("\n" + "="*50 + "\n")
    print(gen.generate_weekly_summary())
