"""Webcal/iCal sync module.

Fetches external calendar feeds and syncs to personal_tasks.
"""

import hashlib
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from urllib.parse import urlparse
import requests


@dataclass
class ICalEvent:
    """Parsed iCal event."""
    uid: str
    summary: str
    start: datetime
    end: Optional[datetime]
    description: Optional[str]
    location: Optional[str]
    sequence: int
    raw_content: str


class ICalParser:
    """Parse iCal format into structured events."""
    
    def parse(self, ical_data: str) -> List[ICalEvent]:
        """Parse iCal data into list of events."""
        events = []
        
        # Split into VEVENT blocks
        vevent_blocks = re.split(r'BEGIN:VEVENT', ical_data)
        
        for block in vevent_blocks[1:]:  # Skip first empty block
            if 'END:VEVENT' not in block:
                continue
            
            event = self._parse_vevent(block)
            if event:
                events.append(event)
        
        return events
    
    def _parse_vevent(self, block: str) -> Optional[ICalEvent]:
        """Parse a single VEVENT block."""
        lines = block.replace('\r\n ', '').replace('\r\n', '\n').split('\n')
        
        data = {
            'uid': None,
            'summary': '',
            'dtstart': None,
            'dtend': None,
            'description': None,
            'location': None,
            'sequence': 0
        }
        
        for line in lines:
            line = line.strip()
            if ':' not in line:
                continue
            
            key, value = line.split(':', 1)
            key = key.split(';')[0]  # Remove parameters
            
            if key == 'UID':
                data['uid'] = value
            elif key == 'SUMMARY':
                data['summary'] = value
            elif key == 'DTSTART':
                data['dtstart'] = self._parse_datetime(value)
            elif key == 'DTEND':
                data['dtend'] = self._parse_datetime(value)
            elif key == 'DESCRIPTION':
                data['description'] = value
            elif key == 'LOCATION':
                data['location'] = value
            elif key == 'SEQUENCE':
                data['sequence'] = int(value)
        
        if not data['uid'] or not data['dtstart']:
            return None
        
        # Calculate hash for change detection
        raw_hash = hashlib.sha256(block.encode()).hexdigest()
        
        return ICalEvent(
            uid=data['uid'],
            summary=data['summary'],
            start=data['dtstart'],
            end=data['dtend'],
            description=data['description'],
            location=data['location'],
            sequence=data['sequence'],
            raw_content=raw_hash
        )
    
    def _parse_datetime(self, value: str) -> datetime:
        """Parse iCal datetime format."""
        # Handle different formats
        # 20260224T090000
        # 20260224T090000Z
        # 20260224 (all-day)
        
        value = value.strip()
        
        if 'T' in value:
            # Has time component
            if value.endswith('Z'):
                # UTC
                return datetime.strptime(value, '%Y%m%dT%H%M%SZ')
            else:
                # Local time
                return datetime.strptime(value[:15], '%Y%m%dT%H%M%S')
        else:
            # All-day event, use start of day
            return datetime.strptime(value, '%Y%m%d')


class WebcalFetcher:
    """Fetch webcal/ical feeds."""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
    
    def fetch(self, url: str) -> str:
        """Fetch iCal data from URL."""
        # Convert webcal:// to http(s)://
        if url.startswith('webcal://'):
            url = url.replace('webcal://', 'https://', 1)
        
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.text


class WebcalSync:
    """Sync external calendars to personal_tasks."""
    
    def __init__(self, storage=None):
        """Initialize with storage."""
        self.parser = ICalParser()
        self.fetcher = WebcalFetcher()
        # Import storage here to avoid circular import
        if storage is None:
            from .storage import TaskStorage
            self.storage = TaskStorage()
        else:
            self.storage = storage
    
    def add_calendar(self, name: str, url: str, **kwargs) -> Dict[str, Any]:
        """Add a new external calendar source."""
        return self.storage.add_external_calendar(name, url, **kwargs)
    
    def sync_calendar(self, calendar_id: str) -> Dict[str, Any]:
        """Sync a single external calendar."""
        # Get calendar details
        calendar = self.storage.get_external_calendar(calendar_id)
        if not calendar:
            return {'error': 'Calendar not found'}
        
        if not calendar['sync_enabled']:
            return {'skipped': True, 'reason': 'Sync disabled'}
        
        try:
            # Fetch iCal data
            ical_data = self.fetcher.fetch(calendar['url'])
            
            # Parse events
            events = self.parser.parse(ical_data)
            
            # Sync each event
            results = {
                'added': 0,
                'updated': 0,
                'unchanged': 0,
                'errors': []
            }
            
            for event in events:
                try:
                    result = self._sync_event(calendar, event)
                    if result['action'] == 'added':
                        results['added'] += 1
                    elif result['action'] == 'updated':
                        results['updated'] += 1
                    else:
                        results['unchanged'] += 1
                except Exception as e:
                    results['errors'].append(f"{event.uid}: {str(e)}")
            
            # Update last sync timestamp
            self.storage.update_calendar_sync_status(
                calendar_id,
                status='success',
                error=None
            )
            
            return results
            
        except Exception as e:
            self.storage.update_calendar_sync_status(
                calendar_id,
                status='error',
                error=str(e)
            )
            return {'error': str(e)}
    
    def _sync_event(self, calendar: Dict, event: ICalEvent) -> Dict[str, Any]:
        """Sync a single event."""
        # Check if event already exists
        existing = self.storage.get_external_event(
            calendar['id'],
            event.uid
        )
        
        if existing:
            # Check if event changed
            if existing['ical_hash'] == event.raw_content:
                return {'action': 'unchanged'}
            
            # Update existing task
            updates = self._event_to_task_data(calendar, event)
            self.storage.update_task(existing['personal_task_id'], **updates)
            
            # Update tracking
            self.storage.update_external_event(
                calendar['id'],
                event.uid,
                ical_hash=event.raw_content,
                ical_sequence=event.sequence
            )
            
            return {'action': 'updated'}
        
        else:
            # Create new task
            task_data = self._event_to_task_data(calendar, event)
            task = self.storage.create_task(**task_data)
            
            # Track the external event
            self.storage.create_external_event(
                calendar_id=calendar['id'],
                personal_task_id=task['id'],
                ical_uid=event.uid,
                ical_hash=event.raw_content,
                ical_sequence=event.sequence
            )
            
            return {'action': 'added'}
    
    def _event_to_task_data(self, calendar: Dict, event: ICalEvent) -> Dict[str, Any]:
        """Convert iCal event to personal_task data."""
        # Determine if timed or all-day
        if event.end and event.end.date() != event.start.date():
            # Multi-day or all-day
            task_type = 'untimed'
            duration = None
        elif event.end:
            task_type = 'timed'
            duration = int((event.end - event.start).total_seconds() / 60)
        else:
            task_type = 'untimed'
            duration = None
        
        # Build description
        description_parts = []
        if event.description:
            description_parts.append(event.description)
        if event.location:
            description_parts.append(f"Location: {event.location}")
        
        return {
            'title': event.summary,
            'task_type': task_type,
            'due_at': event.start,
            'duration_minutes': duration,
            'priority': calendar.get('default_priority') or 'P2',
            'context': calendar.get('default_context') or 'external',
            'description': '\n\n'.join(description_parts) if description_parts else None,
            'source': 'webcal',
            'notes': {
                'external_calendar_id': calendar['id'],
                'external_calendar_name': calendar['name'],
                'ical_uid': event.uid,
                'location': event.location
            }
        }
    
    def sync_all(self) -> List[Dict[str, Any]]:
        """Sync all enabled external calendars."""
        calendars = self.storage.list_external_calendars(sync_enabled=True)
        
        results = []
        for calendar in calendars:
            result = self.sync_calendar(calendar['id'])
            result['calendar_name'] = calendar['name']
            results.append(result)
        
        return results
