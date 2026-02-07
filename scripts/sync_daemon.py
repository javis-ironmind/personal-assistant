#!/usr/bin/env python3
"""Sync daemon for Google Calendar/Tasks.

Run periodically to sync pending tasks to Google.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage import TaskStorage
from src.sync import GoogleSync


def main():
    """Run sync for all pending tasks."""
    storage = TaskStorage()
    sync = GoogleSync()
    
    # Get tasks needing sync
    tasks = storage.get_tasks_needing_sync()
    
    if not tasks:
        print("No tasks to sync.")
        return 0
    
    print(f"Syncing {len(tasks)} tasks to Google...")
    
    success_count = 0
    for task in tasks:
        try:
            result = sync.sync_task(task)
            
            if result['success']:
                # Mark as synced with Google IDs
                storage.mark_synced(
                    task['id'],
                    google_event_id=result.get('google_event_id'),
                    google_task_id=result.get('google_task_id')
                )
                success_count += 1
                print(f"  ✓ {task['title'][:50]}")
            else:
                print(f"  ✗ {task['title'][:50]}: {result['errors']}")
                
        except Exception as e:
            print(f"  ✗ {task['title'][:50]}: {e}")
    
    print(f"\nSynced {success_count}/{len(tasks)} tasks.")
    return 0 if success_count == len(tasks) else 1


if __name__ == "__main__":
    sys.exit(main())
