"""
Tests for newsletter_feed.summarizer module
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from newsletter_feed.summarizer import _generate_summary


class TestSingleDayEventParsing:
    """Tests for single-day event parsing (backward compatibility)"""

    def test_single_day_event_with_times(self):
        """Test that single-day events with times work correctly"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="""
TITLE: Basketball Game

SUMMARY:
Come watch the team play!

EVENTS: 1
---EVENT 1---
TITLE: Basketball Game vs. Oak Hills
DATE: 2025-11-20
TIME: 18:00
END_TIME: 20:00
LOCATION: THS Gymnasium
""")]
        mock_client.messages.create.return_value = mock_response

        pub_date = datetime(2025, 11, 15)

        result = _generate_summary(mock_client, "Game Day", "Basketball game content", [], pub_date)

        assert 'event_info' in result
        assert len(result['event_info']) == 1
        event = result['event_info'][0]
        assert event['start'] == datetime(2025, 11, 20, 18, 0)
        assert event['end'] == datetime(2025, 11, 20, 20, 0)
        assert event['title'] == 'Basketball Game vs. Oak Hills'
        assert event['location'] == 'THS Gymnasium'

    def test_single_day_all_day_event(self):
        """Test all-day single-day event"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="""
TITLE: Professional Development Day

SUMMARY:
No school for students.

EVENTS: 1
---EVENT 1---
TITLE: Professional Development Day
DATE: 2025-11-22
TIME: 00:00
END_TIME: 23:59
LOCATION: Talawanda High School
""")]
        mock_client.messages.create.return_value = mock_response

        pub_date = datetime(2025, 11, 15)

        result = _generate_summary(mock_client, "PD Day", "PD day content", [], pub_date)

        assert 'event_info' in result
        event = result['event_info'][0]
        assert event['start'] == datetime(2025, 11, 22, 0, 0)
        assert event['end'] == datetime(2025, 11, 22, 23, 59)

    def test_single_day_event_unknown_times(self):
        """Test single-day event with unknown times defaults to 1-hour duration"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="""
TITLE: Event

SUMMARY:
Event with no time specified.

EVENTS: 1
---EVENT 1---
TITLE: Test Event
DATE: 2025-11-20
TIME: unknown
END_TIME: unknown
LOCATION: THS
""")]
        mock_client.messages.create.return_value = mock_response

        pub_date = datetime(2025, 11, 15)

        result = _generate_summary(mock_client, "Event", "Content", [], pub_date)

        event = result['event_info'][0]
        assert event['start'] == datetime(2025, 11, 20, 0, 0)
        assert event['end'] == datetime(2025, 11, 20, 1, 0)  # +1 hour default

    def test_single_day_event_with_start_time_only(self):
        """Test single-day event with start time but unknown end time"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="""
TITLE: Meeting

SUMMARY:
Staff meeting.

EVENTS: 1
---EVENT 1---
TITLE: Staff Meeting
DATE: 2025-11-20
TIME: 15:30
END_TIME: unknown
LOCATION: Conference Room
""")]
        mock_client.messages.create.return_value = mock_response

        pub_date = datetime(2025, 11, 15)

        result = _generate_summary(mock_client, "Meeting", "Content", [], pub_date)

        event = result['event_info'][0]
        assert event['start'] == datetime(2025, 11, 20, 15, 30)
        assert event['end'] == datetime(2025, 11, 20, 16, 30)  # +1 hour


class TestMultiDayEventParsing:
    """Tests for multi-day event parsing (new functionality)"""

    def test_multi_day_all_day_event(self):
        """Test multi-day all-day event (e.g., Finals Week)"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="""
TITLE: Finals Week

SUMMARY:
Finals week from December 16-19.

EVENTS: 1
---EVENT 1---
TITLE: Finals Week
DATE: 2025-12-16
END_DATE: 2025-12-19
TIME: 00:00
END_TIME: 23:59
LOCATION: Talawanda High School
""")]
        mock_client.messages.create.return_value = mock_response

        pub_date = datetime(2025, 12, 1)

        result = _generate_summary(mock_client, "Finals Week", "Finals content", [], pub_date)

        assert 'event_info' in result
        assert len(result['event_info']) == 1
        event = result['event_info'][0]
        assert event['start'] == datetime(2025, 12, 16, 0, 0)
        assert event['end'] == datetime(2025, 12, 19, 23, 59)
        assert event['title'] == 'Finals Week'
        # Verify it's actually multi-day
        assert (event['end'].date() - event['start'].date()).days == 3

    def test_multi_day_event_with_specific_times(self):
        """Test multi-day event with specific start and end times"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="""
TITLE: Conference

SUMMARY:
Regional conference Nov 14-16.

EVENTS: 1
---EVENT 1---
TITLE: Regional Education Conference
DATE: 2025-11-14
END_DATE: 2025-11-16
TIME: 08:00
END_TIME: 17:00
LOCATION: Convention Center
""")]
        mock_client.messages.create.return_value = mock_response

        pub_date = datetime(2025, 11, 1)

        result = _generate_summary(mock_client, "Conference", "Content", [], pub_date)

        event = result['event_info'][0]
        assert event['start'] == datetime(2025, 11, 14, 8, 0)
        assert event['end'] == datetime(2025, 11, 16, 17, 0)
        assert (event['end'].date() - event['start'].date()).days == 2

    def test_multi_day_event_no_end_time_defaults_to_end_of_day(self):
        """Test multi-day event without END_TIME uses end of day"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="""
TITLE: Break

SUMMARY:
Thanksgiving break.

EVENTS: 1
---EVENT 1---
TITLE: Thanksgiving Break
DATE: 2025-11-27
END_DATE: 2025-11-29
TIME: 00:00
END_TIME: unknown
LOCATION: Talawanda High School
""")]
        mock_client.messages.create.return_value = mock_response

        pub_date = datetime(2025, 11, 1)

        result = _generate_summary(mock_client, "Break", "Content", [], pub_date)

        event = result['event_info'][0]
        assert event['start'] == datetime(2025, 11, 27, 0, 0)
        assert event['end'] == datetime(2025, 11, 29, 23, 59)  # End of last day


class TestEventParsingEdgeCases:
    """Tests for edge cases and error handling"""

    def test_invalid_end_date_falls_back_to_single_day(self):
        """Test that invalid END_DATE falls back to single-day event"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="""
TITLE: Event

SUMMARY:
Some event.

EVENTS: 1
---EVENT 1---
TITLE: Test Event
DATE: 2025-11-20
END_DATE: invalid-date
TIME: 10:00
END_TIME: 12:00
LOCATION: THS
""")]
        mock_client.messages.create.return_value = mock_response

        pub_date = datetime(2025, 11, 15)

        result = _generate_summary(mock_client, "Event", "Content", [], pub_date)

        assert 'event_info' in result
        assert len(result['event_info']) == 1
        event = result['event_info'][0]
        # Should fallback to single-day event (start + 1 hour)
        assert event['start'] == datetime(2025, 11, 20, 10, 0)
        assert event['end'] == datetime(2025, 11, 20, 11, 0)

    def test_malformed_time_format_skips_event(self):
        """Test that malformed time format causes event to be skipped"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="""
TITLE: Event

SUMMARY:
Event.

EVENTS: 1
---EVENT 1---
TITLE: Test Event
DATE: 2025-11-20
TIME: 10:00
END_TIME: 25:99
LOCATION: THS
""")]
        mock_client.messages.create.return_value = mock_response

        pub_date = datetime(2025, 11, 15)

        result = _generate_summary(mock_client, "Event", "Content", [], pub_date)

        # Malformed END_TIME (25:99 is invalid hour) should cause entire event to be skipped
        # This is expected safe behavior - better to skip than create incorrect event
        assert 'event_info' not in result or len(result.get('event_info', [])) == 0

    def test_missing_date_skips_event(self):
        """Test that events without DATE are skipped"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="""
TITLE: Event

SUMMARY:
Event without date.

EVENTS: 1
---EVENT 1---
TITLE: Test Event
DATE: unknown
TIME: 10:00
END_TIME: 12:00
LOCATION: THS
""")]
        mock_client.messages.create.return_value = mock_response

        pub_date = datetime(2025, 11, 15)

        result = _generate_summary(mock_client, "Event", "Content", [], pub_date)

        # Event should be skipped
        assert 'event_info' not in result or len(result.get('event_info', [])) == 0

    def test_completely_invalid_date_format_skips_event(self):
        """Test that completely invalid date format is handled gracefully"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="""
TITLE: Event

SUMMARY:
Event with bad date.

EVENTS: 1
---EVENT 1---
TITLE: Test Event
DATE: not-a-date
TIME: 10:00
END_TIME: 12:00
LOCATION: THS
""")]
        mock_client.messages.create.return_value = mock_response

        pub_date = datetime(2025, 11, 15)

        result = _generate_summary(mock_client, "Event", "Content", [], pub_date)

        # Should have no events due to parse failure
        assert 'event_info' not in result or len(result.get('event_info', [])) == 0


class TestMultipleEventsParsing:
    """Tests for multiple events in a single item"""

    def test_multiple_single_day_events(self):
        """Test multiple single-day events (e.g., exam schedule)"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="""
TITLE: Exam Schedule

SUMMARY:
Final exams on December 16.

EVENTS: 3
---EVENT 1---
TITLE: Period 1-2 Exam
DATE: 2025-12-16
TIME: 08:00
END_TIME: 09:30
LOCATION: THS

---EVENT 2---
TITLE: Period 3-4 Exam
DATE: 2025-12-16
TIME: 10:00
END_TIME: 11:30
LOCATION: THS

---EVENT 3---
TITLE: Period 5-6 Exam
DATE: 2025-12-16
TIME: 12:30
END_TIME: 14:00
LOCATION: THS
""")]
        mock_client.messages.create.return_value = mock_response

        pub_date = datetime(2025, 12, 1)

        result = _generate_summary(mock_client, "Exams", "Content", [], pub_date)

        assert len(result['event_info']) == 3

        # Verify all events are on same day with different times
        assert result['event_info'][0]['start'] == datetime(2025, 12, 16, 8, 0)
        assert result['event_info'][0]['end'] == datetime(2025, 12, 16, 9, 30)

        assert result['event_info'][1]['start'] == datetime(2025, 12, 16, 10, 0)
        assert result['event_info'][1]['end'] == datetime(2025, 12, 16, 11, 30)

        assert result['event_info'][2]['start'] == datetime(2025, 12, 16, 12, 30)
        assert result['event_info'][2]['end'] == datetime(2025, 12, 16, 14, 0)

    def test_mix_of_single_day_and_multi_day_events(self):
        """Test that an item can have both single-day and multi-day events"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="""
TITLE: Finals Information

SUMMARY:
Finals week and specific exam times.

EVENTS: 2
---EVENT 1---
TITLE: Finals Week
DATE: 2025-12-16
END_DATE: 2025-12-19
TIME: 00:00
END_TIME: 23:59
LOCATION: THS

---EVENT 2---
TITLE: 7th Period Exam
DATE: 2025-12-16
TIME: 13:00
END_TIME: 14:30
LOCATION: THS
""")]
        mock_client.messages.create.return_value = mock_response

        pub_date = datetime(2025, 12, 1)

        result = _generate_summary(mock_client, "Finals", "Content", [], pub_date)

        assert len(result['event_info']) == 2

        # First event should be multi-day
        assert result['event_info'][0]['start'] == datetime(2025, 12, 16, 0, 0)
        assert result['event_info'][0]['end'] == datetime(2025, 12, 19, 23, 59)

        # Second event should be single-day with specific time
        assert result['event_info'][1]['start'] == datetime(2025, 12, 16, 13, 0)
        assert result['event_info'][1]['end'] == datetime(2025, 12, 16, 14, 30)

    def test_zero_events_declared(self):
        """Test that EVENTS: 0 results in no event_info"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="""
TITLE: Information

SUMMARY:
Just informational content, no events.

EVENTS: 0
""")]
        mock_client.messages.create.return_value = mock_response

        pub_date = datetime(2025, 11, 15)

        result = _generate_summary(mock_client, "Info", "Content", [], pub_date)

        # Should not have event_info key
        assert 'event_info' not in result


class TestLocationHandling:
    """Tests for location field handling"""

    def test_explicit_location(self):
        """Test that explicit location is preserved"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="""
TITLE: Game

SUMMARY:
Away game.

EVENTS: 1
---EVENT 1---
TITLE: Basketball Game
DATE: 2025-11-20
TIME: 18:00
END_TIME: 20:00
LOCATION: Oak Hills High School, 123 Main St
""")]
        mock_client.messages.create.return_value = mock_response

        result = _generate_summary(mock_client, "Game", "Content", [], datetime(2025, 11, 15))

        assert result['event_info'][0]['location'] == 'Oak Hills High School, 123 Main St'

    def test_unknown_location_becomes_empty_string(self):
        """Test that 'unknown' location is converted to empty string"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text="""
TITLE: Event

SUMMARY:
Event.

EVENTS: 1
---EVENT 1---
TITLE: Test Event
DATE: 2025-11-20
TIME: 10:00
END_TIME: 12:00
LOCATION: unknown
""")]
        mock_client.messages.create.return_value = mock_response

        result = _generate_summary(mock_client, "Event", "Content", [], datetime(2025, 11, 15))

        assert result['event_info'][0]['location'] == ''
