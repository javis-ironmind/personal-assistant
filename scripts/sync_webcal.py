#!/usr/bin/env python3
"""Webcal/iCal sync script.

Run via cron once daily:
0 6 * * * /usr/bin/python3 /path/to/personal-assistant/scripts/sync_webcal.py

Or sync a specific calendar:
python3 sync_webcal.py --calendar-id <uuid>
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.webcal import WebcalSync
from src.storage import TaskStorage


def main():
    parser = argparse.ArgumentParser(description='Sync external webcal/ical calendars')
    parser.add_argument('--calendar-id', help='Sync specific calendar by ID')
    parser.add_argument('--add', metavar='NAME,URL', help='Add new calendar (format: name,url)')
    parser.add_argument('--context', default='external', help='Default context for imported events')
    parser.add_argument('--priority', default='P2', help='Default priority for imported events')
    parser.add_argument('--list', action='store_true', help='List all external calendars')
    args = parser.parse_args()
    
    storage = TaskStorage()
    sync = WebcalSync(storage)
    
    if args.list:
        calendars = storage.list_external_calendars()
        print(f"External Calendars ({len(calendars)}):")
        for cal in calendars:
            status = "✓" if cal['sync_enabled'] else "✗"
            last_sync = cal['last_synced_at'].strftime('%Y-%m-%d %H:%M') if cal['last_synced_at'] else 'never'
            print(f"  {status} {cal['name']} ({cal['calendar_type']})")
            print(f"     URL: {cal['url'][:60]}...")
            print(f"     Last sync: {last_sync} ({cal.get('last_sync_status', 'unknown')})")
        return 0
    
    if args.add:
        try:
            name, url = args.add.split(',', 1)
            calendar = sync.add_calendar(
                name=name.strip(),
                url=url.strip(),
                default_context=args.context,
                default_priority=args.priority
            )
            print(f"✅ Added calendar: {calendar['name']}")
            print(f"   ID: {calendar['id']}")
            print(f"   URL: {calendar['url'][:60]}...")
        except Exception as e:
            print(f"❌ Error adding calendar: {e}")
            return 1
        return 0
    
    if args.calendar_id:
        # Sync specific calendar
        print(f"Syncing calendar: {args.calendar_id}")
        result = sync.sync_calendar(args.calendar_id)
        
        if 'error' in result:
            print(f"❌ Error: {result['error']}")
            return 1
        
        print(f"✅ Sync complete:")
        print(f"   Added: {result.get('added', 0)}")
        print(f"   Updated: {result.get('updated', 0)}")
        print(f"   Unchanged: {result.get('unchanged', 0)}")
        if result.get('errors'):
            print(f"   Errors: {len(result['errors'])}")
        return 0
    
    # Sync all enabled calendars
    print("Syncing all external calendars...")
    results = sync.sync_all()
    
    total_added = 0
    total_updated = 0
    
    for result in results:
        name = result.get('calendar_name', 'Unknown')
        if 'error' in result:
            print(f"❌ {name}: {result['error']}")
        else:
            added = result.get('added', 0)
            updated = result.get('updated', 0)
            total_added += added
            total_updated += updated
            print(f"✅ {name}: +{added} added, ~{updated} updated")
    
    print(f"\nTotal: {total_added} added, {total_updated} updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
