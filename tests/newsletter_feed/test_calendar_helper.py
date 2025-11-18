"""
Tests for newsletter_feed.calendar_helper module
"""

import pytest
from datetime import datetime
from newsletter_feed.calendar_helper import generate_calendar_links


class TestSingleDayEvents:
    """Tests for single-day event calendar links"""

    def test_single_day_timed_event(self):
        """Test calendar links for single-day event with specific times"""
        event_info = {
            'title': 'Basketball Game',
            'start': datetime(2025, 11, 20, 18, 0),
            'end': datetime(2025, 11, 20, 20, 0),
            'description': 'Come watch the team play!',
            'location': 'THS Gymnasium'
        }

        links = generate_calendar_links(event_info)

        assert 'google' in links
        assert 'ical' in links
        assert 'outlook' in links

        # Google Calendar should have datetime format for timed events
        assert '20251120T180000' in links['google']
        assert '20251120T200000' in links['google']
        assert 'Basketball%20Game' in links['google']

    def test_single_day_all_day_event(self):
        """Test calendar links for single-day all-day event"""
        event_info = {
            'title': 'Professional Development Day',
            'start': datetime(2025, 11, 22, 0, 0),
            'end': datetime(2025, 11, 22, 23, 59),
            'description': 'No school for students',
            'location': 'Talawanda High School'
        }

        links = generate_calendar_links(event_info)

        # All-day events should use date-only format
        assert '20251122' in links['google']
        # Google uses exclusive end date, so should be +1 day
        assert '20251123' in links['google']


class TestMultiDayEvents:
    """Tests for multi-day event calendar links"""

    def test_multi_day_all_day_event(self):
        """Test calendar links for multi-day all-day event (e.g., Finals Week)"""
        event_info = {
            'title': 'Finals Week',
            'start': datetime(2025, 12, 16, 0, 0),
            'end': datetime(2025, 12, 19, 23, 59),
            'description': 'Finals week schedule',
            'location': 'Talawanda High School'
        }

        links = generate_calendar_links(event_info)

        # Multi-day all-day event should use date-only format
        assert '20251216' in links['google']
        # Google uses exclusive end date, so Dec 19 23:59 → Dec 20
        assert '20251220' in links['google']

        # Verify it doesn't have time component (T)
        assert '20251216T' not in links['google']

    def test_multi_day_event_with_times(self):
        """Test calendar links for multi-day event with specific times"""
        event_info = {
            'title': 'Regional Conference',
            'start': datetime(2025, 11, 14, 8, 0),
            'end': datetime(2025, 11, 16, 17, 0),
            'description': 'Education conference',
            'location': 'Convention Center'
        }

        links = generate_calendar_links(event_info)

        # Multi-day timed event should use datetime format
        assert '20251114T080000' in links['google']
        assert '20251116T170000' in links['google']


class TestURLEncoding:
    """Tests for URL encoding in calendar links"""

    def test_special_characters_encoded(self):
        """Test that special characters in event details are properly encoded"""
        event_info = {
            'title': 'Parent/Teacher Conference',
            'start': datetime(2025, 11, 20, 18, 0),
            'end': datetime(2025, 11, 20, 20, 0),
            'description': 'Meet & discuss student progress',
            'location': 'Room #123'
        }

        links = generate_calendar_links(event_info)

        # Verify special characters are encoded
        assert '%20' in links['google']  # Spaces encoded
        assert '%26' in links['google']  # & encoded
        assert '%23' in links['google']  # # encoded

    def test_empty_fields_handled(self):
        """Test that empty description and location fields don't break URLs"""
        event_info = {
            'title': 'Event',
            'start': datetime(2025, 11, 20, 18, 0),
            'end': datetime(2025, 11, 20, 20, 0),
            'description': '',
            'location': ''
        }

        links = generate_calendar_links(event_info)

        # Should generate valid URLs even with empty fields
        assert links['google'].startswith('https://calendar.google.com')
        assert links['outlook'].startswith('https://outlook.live.com')


class TestCalendarServiceFormats:
    """Tests for different calendar service formats"""

    def test_google_calendar_url_structure(self):
        """Test Google Calendar URL has correct structure"""
        event_info = {
            'title': 'Test Event',
            'start': datetime(2025, 11, 20, 10, 0),
            'end': datetime(2025, 11, 20, 11, 0),
            'description': 'Test description',
            'location': 'Test location'
        }

        links = generate_calendar_links(event_info)

        google_url = links['google']
        assert 'calendar.google.com/calendar/render' in google_url
        assert 'action=TEMPLATE' in google_url
        assert 'text=' in google_url
        assert 'dates=' in google_url
        assert 'details=' in google_url
        assert 'location=' in google_url

    def test_ical_data_url_structure(self):
        """Test iCal data URL has correct structure"""
        event_info = {
            'title': 'Test Event',
            'start': datetime(2025, 11, 20, 10, 0),
            'end': datetime(2025, 11, 20, 11, 0),
            'description': 'Test description',
            'location': 'Test location'
        }

        links = generate_calendar_links(event_info)

        ical_url = links['ical']
        assert ical_url.startswith('data:text/calendar')
        assert 'BEGIN%3AVCALENDAR' in ical_url
        assert 'BEGIN%3AVEVENT' in ical_url

    def test_outlook_url_structure(self):
        """Test Outlook URL has correct structure"""
        event_info = {
            'title': 'Test Event',
            'start': datetime(2025, 11, 20, 10, 0),
            'end': datetime(2025, 11, 20, 11, 0),
            'description': 'Test description',
            'location': 'Test location'
        }

        links = generate_calendar_links(event_info)

        outlook_url = links['outlook']
        assert 'outlook.live.com/calendar' in outlook_url
        assert 'subject=' in outlook_url
        assert 'startdt=' in outlook_url
        assert 'enddt=' in outlook_url


class TestEdgeCases:
    """Tests for edge cases in calendar link generation"""

    def test_midnight_event(self):
        """Test event at midnight is handled correctly"""
        event_info = {
            'title': 'Midnight Event',
            'start': datetime(2025, 11, 20, 0, 0),
            'end': datetime(2025, 11, 20, 1, 0),
            'description': 'Event at midnight',
            'location': 'School'
        }

        links = generate_calendar_links(event_info)

        # Should handle midnight (00:00) correctly
        assert '20251120T000000' in links['google']

    def test_end_of_day_event(self):
        """Test event ending at 23:59 is handled correctly"""
        event_info = {
            'title': 'All Day Event',
            'start': datetime(2025, 11, 20, 0, 0),
            'end': datetime(2025, 11, 20, 23, 59),
            'description': 'All day',
            'location': 'School'
        }

        links = generate_calendar_links(event_info)

        # Should be treated as all-day and use date-only format
        assert '20251120' in links['google']
        assert '20251121' in links['google']  # +1 day for exclusive end

    def test_year_boundary_event(self):
        """Test event spanning year boundary"""
        event_info = {
            'title': 'New Year Event',
            'start': datetime(2025, 12, 31, 0, 0),
            'end': datetime(2026, 1, 2, 23, 59),
            'description': 'Spanning new year',
            'location': 'School'
        }

        links = generate_calendar_links(event_info)

        # Should handle year boundary correctly
        assert '20251231' in links['google']
        assert '20260103' in links['google']  # +1 day for exclusive end
