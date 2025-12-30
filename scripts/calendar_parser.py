#!/usr/bin/env python3
"""
Calendar parser for year review.
Parses ICS files and extracts events for the year.
"""

import os
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import zipfile
import tempfile

try:
    from icalendar import Calendar
except ImportError:
    print("icalendar not installed. Install with: pip install icalendar")
    raise


class CalendarParser:
    def __init__(self, calendar_folder: str, year: int = 2025):
        self.calendar_folder = Path(calendar_folder)
        self.year = year
        
    def parse_ics_file(self, file_path: Path) -> List[Dict]:
        """Parse an ICS file and extract events."""
        events = []
        
        # Handle zip files
        if file_path.suffix == '.zip':
            try:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    # Extract to temp directory
                    with tempfile.TemporaryDirectory() as temp_dir:
                        zip_ref.extractall(temp_dir)
                        # Find ICS files in extracted content
                        for extracted_file in Path(temp_dir).rglob('*.ics'):
                            events.extend(self._parse_single_ics(extracted_file))
            except Exception as e:
                print(f"Error extracting zip file {file_path}: {e}")
                return []
        else:
            events = self._parse_single_ics(file_path)
        
        return events
    
    def _parse_single_ics(self, file_path: Path) -> List[Dict]:
        """Parse a single ICS file."""
        events = []
        
        try:
            with open(file_path, 'rb') as f:
                cal = Calendar.from_ical(f.read())
            
            for component in cal.walk():
                if component.name == "VEVENT":
                    event = {}
                    
                    # Get summary/title
                    summary = component.get('summary')
                    if summary:
                        event['title'] = str(summary)
                    else:
                        continue  # Skip events without title
                    
                    # Get dates
                    dtstart = component.get('dtstart')
                    dtend = component.get('dtend')
                    
                    if dtstart:
                        dt = dtstart.dt
                        if isinstance(dt, datetime):
                            event['start'] = dt.isoformat()
                            event['date'] = dt.date().isoformat()
                        else:
                            event['start'] = str(dt)
                            event['date'] = str(dt)
                    
                    if dtend:
                        dt = dtend.dt
                        if isinstance(dt, datetime):
                            event['end'] = dt.isoformat()
                        else:
                            event['end'] = str(dt)
                    
                    # Get description
                    description = component.get('description')
                    if description:
                        event['description'] = str(description)
                    
                    # Get location
                    location = component.get('location')
                    if location:
                        event['location'] = str(location)
                    
                    # Filter by year
                    if 'date' in event:
                        event_year = datetime.fromisoformat(event['date']).year
                        if event_year == self.year:
                            events.append(event)
                            
        except Exception as e:
            print(f"Error parsing ICS file {file_path}: {e}")
        
        return events
    
    def parse_user_calendar(self, calendar_file: str) -> Dict:
        """Parse calendar file for a user."""
        if not calendar_file:
            return {
                'total_events': 0,
                'events_by_month': {},
                'events_by_quarter': {},
                'events': []
            }
        
        file_path = self.calendar_folder / calendar_file
        if not file_path.exists():
            print(f"Calendar file not found: {file_path}")
            return {
                'total_events': 0,
                'events_by_month': {},
                'events_by_quarter': {},
                'events': []
            }
        
        print(f"Parsing calendar file: {calendar_file}")
        events = self.parse_ics_file(file_path)
        
        # Group by month and quarter
        events_by_month = {}
        events_by_quarter = {}
        
        for event in events:
            if 'date' in event:
                try:
                    dt = datetime.fromisoformat(event['date'])
                    month_key = dt.strftime('%Y-%m')
                    quarter = f"Q{(dt.month - 1) // 3 + 1} {self.year}"
                    
                    if month_key not in events_by_month:
                        events_by_month[month_key] = 0
                    events_by_month[month_key] += 1
                    
                    if quarter not in events_by_quarter:
                        events_by_quarter[quarter] = 0
                    events_by_quarter[quarter] += 1
                except:
                    pass
        
        return {
            'total_events': len(events),
            'events_by_month': events_by_month,
            'events_by_quarter': events_by_quarter,
            'events': events
        }


if __name__ == "__main__":
    import sys
    import json
    from pathlib import Path
    
    # Load config
    config_path = Path(__file__).parent.parent / "config" / "team_config.json"
    with open(config_path) as f:
        config = json.load(f)
    
    parser = CalendarParser(config['calendar_folder'], config['year'])
    
    # Test with first member
    if len(sys.argv) > 1:
        calendar_file = sys.argv[1]
        data = parser.parse_user_calendar(calendar_file)
        print(json.dumps(data, indent=2, default=str))
    else:
        # Test with all members
        for member in config['members']:
            if member.get('has_calendar') and member.get('calendar_file'):
                print(f"\n=== {member['name']} ===")
                data = parser.parse_user_calendar(member['calendar_file'])
                print(f"Total events: {data['total_events']}")

