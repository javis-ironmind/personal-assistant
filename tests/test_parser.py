"""Tests for the task parser."""

import pytest
from datetime import datetime
import pytz

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.parser import TaskParser, parse_task


class TestTaskParser:
    """Test cases for natural language task parsing."""
    
    @pytest.fixture
    def parser(self):
        return TaskParser("America/Los_Angeles")
    
    def test_parse_meeting_with_time(self, parser):
        """Parse meeting with specific time."""
        result = parser.parse("Meeting with Sarah tomorrow 2pm for 30 min")
        
        assert result.title == "Meeting with Sarah"
        assert result.task_type == "timed"
        assert result.duration_minutes == 30
        assert result.due_at is not None
    
    def test_parse_priority_task(self, parser):
        """Parse task with priority."""
        result = parser.parse("P0 finish taxes by April 1")
        
        assert result.title == "finish taxes"
        assert result.priority == "P0"
        assert result.task_type == "deadline"
    
    def test_parse_reminder(self, parser):
        """Parse reminder without specific time."""
        result = parser.parse("Remind me to call mom Friday")
        
        assert "call mom" in result.title.lower()
        assert result.task_type in ("reminder", "deadline")
    
    def test_parse_note(self, parser):
        """Parse note prefix."""
        result = parser.parse("Note: Idea for startup")
        
        assert "Idea for startup" in result.title
        assert result.task_type == "note"
        assert result.due_at is None
    
    def test_parse_recurring(self, parser):
        """Parse recurring task."""
        result = parser.parse("Daily standup 9am recurring")
        
        assert "standup" in result.title.lower()
        assert result.recurring_rule == "daily"
        assert result.task_type == "timed"
    
    def test_parse_with_context(self, parser):
        """Parse task with hashtag context."""
        result = parser.parse("Book flight to Taiwan #travel")
        
        assert "Book flight to Taiwan" in result.title
        assert result.context == "travel"
    
    def test_parse_duration_hours(self, parser):
        """Parse duration in hours."""
        result = parser.parse("Meeting for 2 hours")
        
        assert result.duration_minutes == 120


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
