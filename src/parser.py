"""Natural language parser for tasks.

Converts free-form text into structured task data.
"""

import re
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, Dict, Any
import dateparser
import pytz


@dataclass
class ParsedTask:
    """Structured task from natural language input."""
    title: str
    task_type: str  # 'timed', 'untimed', 'deadline', 'reminder', 'note'
    due_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    priority: Optional[str] = None  # 'P0', 'P1', 'P2', 'P3'
    context: Optional[str] = None
    recurring_rule: Optional[str] = None
    description: Optional[str] = None


class TaskParser:
    """Parse natural language into structured tasks."""
    
    PRIORITY_PATTERN = re.compile(r'\b(P0|P1|P2|P3)\b', re.IGNORECASE)
    DURATION_PATTERN = re.compile(r'\bfor\s+(\d+)\s*(min|minute|minutes|hr|hour|hours)\b', re.IGNORECASE)
    RECURRING_PATTERN = re.compile(r'\b(daily|weekly|monthly|every\s+(day|week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b', re.IGNORECASE)
    CONTEXT_PATTERN = re.compile(r'#(\w+)', re.IGNORECASE)
    
    def __init__(self, timezone: str = "America/Los_Angeles"):
        self.timezone = pytz.timezone(timezone)
        self.now = datetime.now(self.timezone)
    
    def parse(self, text: str) -> ParsedTask:
        """Parse natural language text into a ParsedTask."""
        text = text.strip()
        
        # Extract priority
        priority = self._extract_priority(text)
        
        # Extract duration
        duration = self._extract_duration(text)
        
        # Extract recurring rule
        recurring = self._extract_recurring(text)
        
        # Extract context hashtags
        context = self._extract_context(text)
        
        # Determine task type and parse dates
        task_type, due_at = self._extract_datetime(text)
        
        # Clean title (remove parsed elements)
        title = self._clean_title(text)
        
        return ParsedTask(
            title=title,
            task_type=task_type,
            due_at=due_at,
            duration_minutes=duration,
            priority=priority,
            context=context,
            recurring_rule=recurring
        )
    
    def _extract_priority(self, text: str) -> Optional[str]:
        """Extract P0-P4 priority from text."""
        match = self.PRIORITY_PATTERN.search(text)
        return match.group(1).upper() if match else None
    
    def _extract_duration(self, text: str) -> Optional[int]:
        """Extract duration in minutes from text."""
        match = self.DURATION_PATTERN.search(text)
        if not match:
            return None
        
        value = int(match.group(1))
        unit = match.group(2).lower()
        
        if unit in ('hr', 'hour', 'hours'):
            return value * 60
        return value
    
    def _extract_recurring(self, text: str) -> Optional[str]:
        """Extract recurring pattern from text."""
        match = self.RECURRING_PATTERN.search(text)
        if not match:
            return None
        
        recurring_text = match.group(0).lower()
        
        # Normalize recurring patterns
        if 'daily' in recurring_text or 'every day' in recurring_text:
            return 'daily'
        elif 'weekly' in recurring_text or 'every week' in recurring_text:
            return 'weekly'
        elif 'monthly' in recurring_text or 'every month' in recurring_text:
            return 'monthly'
        elif 'every' in recurring_text:
            # Extract day of week
            days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            for day in days:
                if day in recurring_text:
                    return f'weekly:{day}'
        
        return None
    
    def _extract_context(self, text: str) -> Optional[str]:
        """Extract context hashtags from text."""
        match = self.CONTEXT_PATTERN.search(text)
        return match.group(1).lower() if match else None
    
    def _extract_datetime(self, text: str) -> tuple:
        """Extract datetime and determine task type."""
        # Check for note prefix
        if text.lower().startswith('note:'):
            return 'note', None
        
        # Check for reminder keywords without specific time
        reminder_keywords = ['remind me', 'reminder', 'remember to', "don't forget"]
        is_reminder = any(kw in text.lower() for kw in reminder_keywords)
        
        # Parse dates using dateparser
        settings = {
            'RELATIVE_BASE': self.now,
            'RETURN_AS_TIMEZONE_AWARE': True,
            'TIMEZONE': str(self.timezone),
            'PREFER_DATES_FROM': 'future'
        }
        
        parsed_date = dateparser.parse(text, settings=settings)
        
        if not parsed_date:
            # No date found
            if is_reminder:
                return 'reminder', None
            return 'untimed', None
        
        # Ensure timezone-aware
        if parsed_date.tzinfo is None:
            parsed_date = self.timezone.localize(parsed_date)
        
        # Determine type based on time specificity
        has_specific_time = any(word in text.lower() for word in 
                                ['at ', 'am', 'pm', ':', 'o\'clock', 'morning', 'afternoon', 'evening'])
        
        if has_specific_time:
            return 'timed', parsed_date
        else:
            # Date only = deadline
            return 'deadline', parsed_date
    
    def _clean_title(self, text: str) -> str:
        """Remove parsed elements to get clean title."""
        # Remove priority
        text = self.PRIORITY_PATTERN.sub('', text)
        
        # Remove duration
        text = self.DURATION_PATTERN.sub('', text)
        
        # Remove recurring
        text = self.RECURRING_PATTERN.sub('', text)
        
        # Remove context hashtags
        text = self.CONTEXT_PATTERN.sub('', text)
        
        # Remove date/time expressions (common patterns)
        date_patterns = [
            r'\btomorrow\b',
            r'\btoday\b',
            r'\bnext week\b',
            r'\bthis week\b',
            r'\bon (monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
            r'\bat \d{1,2}(?::\d{2})?\s*(?:am|pm)?\b',
            r'\bby\s+\w+\b',
            r'\bremind me\s+(?:to\s+)?',
            r'\bnote:\s*',
        ]
        
        for pattern in date_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'^[\s,]+|[\s,]+$', '', text)
        
        return text


def parse_task(text: str, timezone: str = "America/Los_Angeles") -> ParsedTask:
    """Convenience function to parse a task."""
    parser = TaskParser(timezone)
    return parser.parse(text)


# Example usage for testing
if __name__ == "__main__":
    test_inputs = [
        "Meeting with Sarah tomorrow 2pm for 30 min",
        "P0 finish taxes by April 1",
        "Remind me to call mom Friday",
        "Note: Idea for startup",
        "Daily standup 9am recurring",
        "Book flight to Taiwan #travel",
        "What do I have today?",
    ]
    
    for text in test_inputs:
        result = parse_task(text)
        print(f"\nInput: {text}")
        print(f"  Title: {result.title}")
        print(f"  Type: {result.task_type}")
        print(f"  Due: {result.due_at}")
        print(f"  Duration: {result.duration_minutes} min")
        print(f"  Priority: {result.priority}")
        print(f"  Context: {result.context}")
        print(f"  Recurring: {result.recurring_rule}")
