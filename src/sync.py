"""Google Calendar and Tasks sync module.

One-way sync: PostgreSQL → Google (source of truth is DB)
"""

import os
from typing import Optional, Dict, Any
from datetime import datetime

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle


class GoogleSync:
    """Sync tasks to Google Calendar and Tasks."""
    
    SCOPES = [
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/tasks'
    ]
    
    def __init__(self, 
                 client_secret_path: str = None,
                 account: str = None,
                 token_path: str = None):
        """Initialize Google API clients."""
        self.client_secret_path = client_secret_path or os.getenv(
            'GOOGLE_CLIENT_SECRET_PATH', 
            '/home/ubuntu/.openclaw/credentials/client_secret.json'
        )
        self.account = account or os.getenv('GOOGLE_ACCOUNT', 'nivlek99@gmail.com')
        self.token_path = token_path or f'/tmp/pa_token_{self.account.replace("@", "_")}.pickle'
        
        self.creds = None
        self.calendar_service = None
        self.tasks_service = None
        
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google APIs."""
        # Load existing token
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                self.creds = pickle.load(token)
        
        # Refresh or create new token
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                # Note: In production, this should use existing gog credentials
                # or a service account. This is simplified for initial implementation.
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secret_path, self.SCOPES)
                self.creds = flow.run_local_server(port=0)
            
            # Save token
            with open(self.token_path, 'wb') as token:
                pickle.dump(self.creds, token)
        
        # Build services
        self.calendar_service = build('calendar', 'v3', credentials=self.creds)
        self.tasks_service = build('tasks', 'v1', credentials=self.creds)
    
    def sync_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Sync a single task to Google."""
        result = {
            'task_id': task['id'],
            'success': False,
            'google_event_id': None,
            'google_task_id': None,
            'errors': []
        }
        
        try:
            task_type = task.get('type')
            
            # Sync to Calendar if timed or deadline
            if task_type in ('timed', 'deadline') and task.get('due_at'):
                event_id = self._sync_to_calendar(task)
                result['google_event_id'] = event_id
            
            # Sync to Tasks for all actionable items
            if task_type in ('timed', 'untimed', 'deadline', 'reminder'):
                gtask_id = self._sync_to_tasks(task)
                result['google_task_id'] = gtask_id
            
            result['success'] = True
            
        except Exception as e:
            result['errors'].append(str(e))
        
        return result
    
    def _sync_to_calendar(self, task: Dict[str, Any]) -> Optional[str]:
        """Create or update Calendar event."""
        existing_event_id = task.get('google_event_id')
        
        # Build event body
        event_body = self._build_calendar_event(task)
        
        if existing_event_id:
            # Update existing
            try:
                event = self.calendar_service.events().update(
                    calendarId='primary',
                    eventId=existing_event_id,
                    body=event_body
                ).execute()
                return event['id']
            except Exception:
                # Event may have been deleted, create new
                existing_event_id = None
        
        if not existing_event_id:
            # Create new event
            event = self.calendar_service.events().insert(
                calendarId='primary',
                body=event_body
            ).execute()
            return event['id']
        
        return existing_event_id
    
    def _build_calendar_event(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Build Calendar event body from task."""
        due_at = task.get('due_at')
        duration = task.get('duration_minutes', 30)
        
        if isinstance(due_at, str):
            due_at = datetime.fromisoformat(due_at.replace('Z', '+00:00'))
        
        # Format for Google Calendar API
        if task.get('type') == 'deadline':
            # All-day event for deadlines
            start = {'date': due_at.strftime('%Y-%m-%d')}
            end = {'date': (due_at + __import__('datetime').timedelta(days=1)).strftime('%Y-%m-%d')}
        else:
            # Timed event
            start_dt = due_at
            end_dt = due_at + __import__('datetime').timedelta(minutes=duration)
            
            start = {
                'dateTime': start_dt.isoformat(),
                'timeZone': str(__import__('pytz').timezone('America/Los_Angeles'))
            }
            end = {
                'dateTime': end_dt.isoformat(),
                'timeZone': str(__import__('pytz').timezone('America/Los_Angeles'))
            }
        
        # Build description with metadata
        description = task.get('description', '')
        description += f"\n\n[PA Task ID: {task['id']}]"
        if task.get('priority'):
            description += f"\nPriority: {task['priority']}"
        if task.get('context'):
            description += f"\nContext: {task['context']}"
        
        event = {
            'summary': task['title'],
            'description': description.strip(),
            'start': start,
            'end': end,
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 15}
                ]
            }
        }
        
        # Add color based on priority
        priority_colors = {
            'P0': '11',  # Red
            'P1': '6',   # Orange
            'P2': '2',   # Green
            'P3': '8',   # Gray
        }
        if task.get('priority') in priority_colors:
            event['colorId'] = priority_colors[task['priority']]
        
        return event
    
    def _sync_to_tasks(self, task: Dict[str, Any]) -> Optional[str]:
        """Create or update Google Task."""
        existing_task_id = task.get('google_task_id')
        
        # Get or create task list
        tasklist_id = self._get_default_tasklist()
        
        # Build task body
        task_body = self._build_google_task(task)
        
        if existing_task_id:
            try:
                gtask = self.tasks_service.tasks().update(
                    tasklist=tasklist_id,
                    task=existing_task_id,
                    body=task_body
                ).execute()
                return gtask['id']
            except Exception:
                existing_task_id = None
        
        if not existing_task_id:
            gtask = self.tasks_service.tasks().insert(
                tasklist=tasklist_id,
                body=task_body
            ).execute()
            return gtask['id']
        
        return existing_task_id
    
    def _build_google_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Build Google Task body from task."""
        gtask = {
            'title': task['title'],
            'notes': task.get('description', '')
        }
        
        # Add due date if present
        if task.get('due_at'):
            due_at = task['due_at']
            if isinstance(due_at, str):
                due_at = datetime.fromisoformat(due_at.replace('Z', '+00:00'))
            gtask['due'] = due_at.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        
        # Mark completed if done
        if task.get('status') == 'done':
            gtask['status'] = 'completed'
            gtask['completed'] = task.get('completed_at') or datetime.utcnow().isoformat()
        
        return gtask
    
    def _get_default_tasklist(self) -> str:
        """Get default task list ID."""
        tasklists = self.tasks_service.tasklists().list(maxResults=1).execute()
        return tasklists['items'][0]['id'] if tasklists.get('items') else '@default'
    
    def delete_from_google(self, 
                          google_event_id: Optional[str] = None,
                          google_task_id: Optional[str] = None):
        """Delete task from Google services."""
        if google_event_id:
            try:
                self.calendar_service.events().delete(
                    calendarId='primary',
                    eventId=google_event_id
                ).execute()
            except Exception:
                pass  # Already deleted
        
        if google_task_id:
            try:
                tasklist_id = self._get_default_tasklist()
                self.tasks_service.tasks().delete(
                    tasklist=tasklist_id,
                    task=google_task_id
                ).execute()
            except Exception:
                pass  # Already deleted


# Compatibility imports
timedelta = __import__('datetime').timedelta
pytz = __import__('pytz')
