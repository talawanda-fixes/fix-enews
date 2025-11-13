"""
Helper functions for generating calendar links from event items
"""

from typing import Dict, Optional
from datetime import datetime, timedelta
import re
from urllib.parse import quote


def extract_event_info(item: Dict) -> Optional[Dict]:
    """
    Try to extract event information from an item
    
    Args:
        item: News item dictionary
        
    Returns:
        Dictionary with event info (title, start, end, description, location) or None
    """
    title = item.get('title', '')
    content = item.get('content', '')
    
    # Combine blocks content for searching
    blocks_text = ""
    for block in item.get('blocks', []):
        if 'content' in block:
            blocks_text += block['content'] + "\n"
    
    search_text = f"{title}\n{content}\n{blocks_text}"
    
    # Look for date/time patterns
    # Common patterns: "November 15", "Nov 15", "11/15", "November 15 at 6:00 PM"
    event_patterns = [
        r'(\w+ \d{1,2}(?:st|nd|rd|th)?(?:,? \d{4})?)\s+(?:at|@)\s+(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))',
        r'(\d{1,2}/\d{1,2}/\d{2,4})\s+(?:at|@)\s+(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))',
    ]
    
    for pattern in event_patterns:
        match = re.search(pattern, search_text, re.IGNORECASE)
        if match:
            date_str = match.group(1)
            time_str = match.group(2) if len(match.groups()) > 1 else None
            
            # Try to parse the date
            try:
                event_datetime = parse_event_datetime(date_str, time_str)
                if event_datetime:
                    # Extract location if present
                    location = extract_location(search_text)
                    
                    # Create event info
                    return {
                        'title': title,
                        'start': event_datetime,
                        'end': event_datetime + timedelta(hours=1),  # Default 1 hour duration
                        'description': content[:200] if content else '',
                        'location': location or ''
                    }
            except Exception:
                continue
    
    return None


def parse_event_datetime(date_str: str, time_str: Optional[str] = None) -> Optional[datetime]:
    """Parse date and time strings into datetime object"""
    # TODO: Implement proper date/time parsing
    # For now, return None - we'll need to handle various formats
    return None


def extract_location(text: str) -> Optional[str]:
    """Try to extract location from text"""
    # Look for common location indicators
    location_patterns = [
        r'(?:at|@|location:?)\s+([A-Z][^.!?\n]{10,50})',
        r'(?:room|gym|auditorium|cafeteria)\s+([A-Z0-9]+)',
    ]
    
    for pattern in location_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return None


def generate_calendar_links(event_info: Dict) -> Dict[str, str]:
    """
    Generate calendar links for different calendar services
    
    Args:
        event_info: Dictionary with title, start, end, description, location
        
    Returns:
        Dictionary with 'google', 'ical', 'outlook' keys and their URLs
    """
    title = quote(event_info['title'])
    description = quote(event_info.get('description', ''))
    location = quote(event_info.get('location', ''))
    
    start = event_info['start']
    end = event_info['end']
    
    # Format dates for different services
    start_google = start.strftime('%Y%m%dT%H%M%S')
    end_google = end.strftime('%Y%m%dT%H%M%S')
    
    start_ical = start.strftime('%Y%m%dT%H%M%S')
    end_ical = end.strftime('%Y%m%dT%H%M%S')
    
    # Google Calendar
    google_url = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={title}&dates={start_google}/{end_google}&details={description}&location={location}"
    
    # iCal format (for Apple Calendar, etc.)
    ical_content = f"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:{start_ical}
DTEND:{end_ical}
SUMMARY:{event_info['title']}
DESCRIPTION:{event_info.get('description', '')}
LOCATION:{event_info.get('location', '')}
END:VEVENT
END:VCALENDAR"""
    
    # For iCal, we'd need to create a data URL or downloadable file
    ical_url = f"data:text/calendar;charset=utf-8,{quote(ical_content)}"
    
    # Outlook.com
    outlook_url = f"https://outlook.live.com/calendar/0/deeplink/compose?subject={title}&startdt={start_google}&enddt={end_google}&body={description}&location={location}"
    
    return {
        'google': google_url,
        'ical': ical_url,
        'outlook': outlook_url
    }


def add_calendar_link_to_item(item: Dict) -> Dict:
    """
    Add calendar link to item if it appears to be an event
    
    Args:
        item: News item dictionary
        
    Returns:
        Modified item with 'calendar_links' field if event detected
    """
    event_info = extract_event_info(item)
    
    if event_info:
        calendar_links = generate_calendar_links(event_info)
        item['calendar_links'] = calendar_links
        item['is_event'] = True
    
    return item
