from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from youtube.models import YouTubeToken
from youtube.tasks import update_all_users_youtube_stats
from django.contrib.auth import get_user_model

User = get_user_model()

class YouTubeTasksTest(TestCase):

    @patch('youtube.tasks.update_channel_and_video_stats')
    def test_update_all_users_youtube_stats(self, mock_update_stats):
        user = User.objects.create_user(email='testuser@example.com', password='testpass')
        YouTubeToken.objects.create(
            user=user,
            access_token='token',
            refresh_token='refresh',
            token_expiry=timezone.now() + timezone.timedelta(hours=1)
        )

        update_all_users_youtube_stats()

        self.assertTrue(mock_update_stats.called)
