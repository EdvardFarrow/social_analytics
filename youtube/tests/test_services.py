from django.test import TestCase
from unittest.mock import patch
from youtube.services import fetch_youtube_channel_stats, refresh_access_token
from django.utils import timezone
from datetime import timedelta

class YouTubeServicesTest(TestCase):

    @patch('youtube.services.requests.get')
    def test_fetch_youtube_channel_stats_success(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            'items': [{
                'snippet': {'title': 'My Channel'},
                'statistics': {
                    'subscriberCount': '1000',
                    'viewCount': '50000',
                    'videoCount': '150'
                }
            }]
        }

        stats = fetch_youtube_channel_stats('fake_token', 'fake_channel_id')
        self.assertEqual(stats['title'], 'My Channel')
        self.assertEqual(stats['subscriber_count'], 1000)
        self.assertEqual(stats['view_count'], 50000)
        self.assertEqual(stats['video_count'], 150)

    @patch('youtube.services.requests.post')
    def test_refresh_access_token_success(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'access_token': 'new_access_token',
            'expires_in': 3600
        }

        class DummyToken:
            access_token = 'old_access_token'
            refresh_token = 'refresh_token'
            token_expiry = timezone.now() + timedelta(hours=1),
            def save(self): pass

        dummy_token = DummyToken()
        dummy_token.token_expiry = None  # force refresh
        dummy_token.token_expiry = timezone.now() - timedelta(seconds=10)  
        dummy_token.access_token = 'old_access_token'
        dummy_token.refresh_token = 'refresh_token'
        dummy_token.save()

        new_token = refresh_access_token(dummy_token)
        self.assertEqual(new_token, 'new_access_token')
