"""Interactive query handlers.

Process natural language queries about tasks.
"""

import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from storage import TaskStorage


class QueryHandler:
    """Handle interactive queries about tasks."""
    
    def __init__(self, storage: TaskStorage = None):
        """Initialize with storage."""
        self.storage = storage or TaskStorage()
    
    def handle(self, query: str) -> str:
        """Process a query and return response."""
        query = query.lower().strip()
        
        # Pattern matching for common queries
        if self._matches(query, [
            "what do i have today",
            "what's on today",
            "what is on today",
            "today's schedule",
            "schedule today"
        ]):
            return self._today_schedule()
        
        if self._matches(query, [
            "what's overdue",
            "what is overdue",
            "overdue tasks",
            "late tasks"
        ]):
            return self._overdue_tasks()
        
        if self._matches(query, [
            "done this week",
            "completed this week",
            "what did i do this week",
            "weekly summary"
        ]):
            return self._weekly_completed()
        
        if self._matches(query, [
            "p0 items",
            "priority 0",
            "high priority",
            "urgent tasks"
        ]):
            return self._high_priority_tasks()
        
        if self._matches(query, [
            "all tasks",
            "list all",
            "show all tasks"
        ]):
            return self._all_tasks()
        
        # Context-specific queries: "what about <context>"
        context_match = re.search(r'what about\s+(\w+)', query)
        if context_match:
            context = context_match.group(1)
            return self._context_tasks(context)
        
        # Search by title: "when is <title>"
        when_match = re.search(r'when is\s+(.+)', query)
        if when_match:
            title_fragment = when_match.group(1)
            return self._find_task_by_title(title_fragment)
        
        # Priority-specific queries
        priority_match = re.search(r'\b(p0|p1|p2|p3)\s+tasks?\b', query)
        if priority_match:
            priority = priority_match.group(1).upper()
            return self._priority_tasks(priority)
        
        # Help
        if self._matches(query, ["help", "commands", "what can you do"]):
            return self._help_text()
        
        # Unknown query
        return "I'm not sure what you're asking. Try: 'what do I have today?' or 'help'"
    
    def _matches(self, query: str, patterns: List[str]) -> bool:
        """Check if query matches any pattern."""
        return any(pattern in query for pattern in patterns)
    
    def _today_schedule(self) -> str:
        """Get today's schedule."""
        today = datetime.now()
        today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        timed = self.storage.list_tasks(
            due_after=today_start,
            due_before=today_end,
            status='todo'
        )
        
        if not timed:
            return "✨ Nothing scheduled for today."
        
        lines = [f"📅 Today ({today.strftime('%A, %b %d')}):", ""]
        
        for item in sorted(timed, key=lambda x: x['due_at'] or ''):
            time_str = self._format_time(item.get('due_at'))
            p = item.get('priority', '')
            p_str = f"[{p}] " if p else ""
            lines.append(f"  {time_str} {p_str}{item['title']}")
        
        return "\n".join(lines)
    
    def _overdue_tasks(self) -> str:
        """Get overdue tasks."""
        overdue = self.storage.get_overdue_tasks()
        
        if not overdue:
            return "✅ No overdue tasks!"
        
        lines = [f"🔴 Overdue Tasks ({len(overdue)}):", ""]
        
        for item in overdue[:10]:
            due_str = self._format_relative_date(item.get('due_at'))
            p = item.get('priority', '')
            p_str = f"[{p}] " if p else ""
            lines.append(f"  {p_str}{item['title']} (due {due_str})")
        
        if len(overdue) > 10:
            lines.append(f"\n  ... and {len(overdue) - 10} more")
        
        return "\n".join(lines)
    
    def _weekly_completed(self) -> str:
        """Get tasks completed this week."""
        completed = self.storage.get_weekly_completed()
        
        if not completed:
            return "No tasks completed this week yet."
        
        lines = [f"✅ Completed This Week ({len(completed)}):", ""]
        
        for item in completed[:10]:
            lines.append(f"  • {item['title']}")
        
        if len(completed) > 10:
            lines.append(f"\n  ... and {len(completed) - 10} more")
        
        return "\n".join(lines)
    
    def _high_priority_tasks(self) -> str:
        """Get P0/P1 priority tasks."""
        tasks = self.storage.list_tasks(priority='P0', status='todo')
        
        if not tasks:
            return "No P0 (highest priority) tasks pending."
        
        lines = [f"🔥 P0 Priority Tasks ({len(tasks)}):", ""]
        
        for item in tasks[:10]:
            due_str = self._format_relative_date(item.get('due_at'))
            due_part = f" (due {due_str})" if due_str else ""
            lines.append(f"  • {item['title']}{due_part}")
        
        return "\n".join(lines)
    
    def _priority_tasks(self, priority: str) -> str:
        """Get tasks by specific priority."""
        tasks = self.storage.list_tasks(priority=priority, status='todo')
        
        if not tasks:
            return f"No {priority} priority tasks pending."
        
        lines = [f"📌 {priority} Priority Tasks ({len(tasks)}):", ""]
        
        for i, item in enumerate(tasks[:15], 1):
            lines.append(f"  {i}. {item['title']}")
        
        if len(tasks) > 15:
            lines.append(f"\n  ... and {len(tasks) - 15} more")
        
        return "\n".join(lines)
    
    def _context_tasks(self, context: str) -> str:
        """Get tasks by context."""
        tasks = self.storage.list_tasks(context=context, status='todo')
        
        if not tasks:
            return f"No tasks found with context '{context}'."
        
        lines = [f"📁 Tasks for #{context} ({len(tasks)}):", ""]
        
        for item in tasks[:15]:
            p = item.get('priority', '')
            p_str = f"[{p}] " if p else ""
            lines.append(f"  • {p_str}{item['title']}")
        
        return "\n".join(lines)
    
    def _all_tasks(self) -> str:
        """Get all pending tasks."""
        tasks = self.storage.list_tasks(status='todo', limit=50)
        
        if not tasks:
            return "✨ No pending tasks!"
        
        lines = [f"📝 All Pending Tasks ({len(tasks)}):", ""]
        
        for i, item in enumerate(tasks[:20], 1):
            p = item.get('priority', '')
            p_str = f"[{p}] " if p else ""
            due_str = self._format_relative_date(item.get('due_at'))
            due_part = f" ({due_str})" if due_str else ""
            lines.append(f"  {i}. {p_str}{item['title']}{due_part}")
        
        if len(tasks) > 20:
            lines.append(f"\n  ... and {len(tasks) - 20} more")
        
        return "\n".join(lines)
    
    def _find_task_by_title(self, title_fragment: str) -> str:
        """Find task by title fragment."""
        # Search all tasks (inefficient but works for now)
        tasks = self.storage.list_tasks(status='todo', limit=100)
        
        matches = [
            t for t in tasks 
            if title_fragment.lower() in t['title'].lower()
        ]
        
        if not matches:
            return f"No task found matching '{title_fragment}'."
        
        if len(matches) == 1:
            item = matches[0]
            due_str = self._format_relative_date(item.get('due_at'))
            due_part = f" on {due_str}" if due_str else ""
            return f"📌 '{item['title']}' is scheduled{due_part}."
        
        lines = [f"Found {len(matches)} matching tasks:", ""]
        for item in matches[:5]:
            due_str = self._format_relative_date(item.get('due_at'))
            due_part = f" ({due_str})" if due_str else ""
            lines.append(f"  • {item['title']}{due_part}")
        
        return "\n".join(lines)
    
    def _format_time(self, dt) -> str:
        """Format datetime as HH:MM."""
        if dt is None:
            return "??:??"
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        return dt.strftime('%H:%M')
    
    def _format_relative_date(self, dt) -> Optional[str]:
        """Format datetime as relative date."""
        if dt is None:
            return None
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        
        if dt.date() == today.date():
            return "today"
        elif dt.date() == tomorrow.date():
            return "tomorrow"
        elif dt < now:
            delta = now - dt
            if delta.days == 0:
                return "today"
            elif delta.days == 1:
                return "yesterday"
            else:
                return f"{delta.days} days ago"
        else:
            delta = dt - now
            if delta.days == 1:
                return "tomorrow"
            else:
                return dt.strftime('%b %d')
    
    def _help_text(self) -> str:
        """Return help text."""
        return """🤖 I can help you manage tasks. Here are some things you can ask:

**Queries:**
  • "What do I have today?" - Today's schedule
  • "What's overdue?" - Late tasks
  • "Done this week?" - Weekly summary
  • "P0 items?" - High priority tasks
  • "What about work?" - Tasks by context
  • "When is the Sarah meeting?" - Find task by name

**Actions:**
  • "Meeting with Sarah tomorrow 2pm for 30 min"
  • "P0 finish taxes by April 1"
  • "Remind me to call mom Friday"
  • "Done 1, 3, 5" - Mark tasks complete
  • "Note: idea for startup"

Just type naturally and I'll understand!
"""


if __name__ == "__main__":
    # Test queries
    handler = QueryHandler()
    test_queries = [
        "what do i have today",
        "what's overdue",
        "p0 items",
        "help"
    ]
    for q in test_queries:
        print(f"\nQ: {q}")
        print(handler.handle(q))
