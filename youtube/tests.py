from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
import json
from django.conf import settings
from google.oauth2.credentials import Credentials as GoogleCredentialsClass

from accounts.models import CustomUser, GoogleCredentials
from .models import YouTubeChannel, YoutubeDailyStats, YouTubeVideo, YoutubeAudienceDemographics

class YouTubeViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(email='testuser@example.com', password='testpassword')
        self.credentials = GoogleCredentials.objects.create(
            user=self.user,
            access_token='fake_access_token',
            refresh_token='fake_refresh_token',
            token_expiry=timezone.now() + timedelta(hours=1),
            scopes=' '.join(settings.YOUTUBE_SCOPES),
            client_id=settings.YOUTUBE_CLIENT_ID,
            client_secret=settings.YOUTUBE_CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token",
        )
        self.channel = YouTubeChannel.objects.create(
            user=self.user,
            channel_id='UC_test_channel_id',
            title='Test Channel'
        )
        
        # Создаем тестовые данные для графиков
        self.today = date.today()
        for i in range(5):
            day = self.today - timedelta(days=i)
            YoutubeDailyStats.objects.create(
                channel=self.channel,
                date=day,
                views=100 + i,
                subscribers_gained=5 + i,
                subscribers_lost=1
            )
        
        # Создаем тестовые данные для видео
        for i in range(3):
            YouTubeVideo.objects.create(
                channel=self.channel,
                video_id=f'test_video_{i}',
                title=f'Test Video {i}',
                published_at=timezone.now() - timedelta(days=i),
                views=1000 + i,
                likes=50 + i,
                comments=10 + i
            )
        
        # Создаем тестовые данные для демографии
        YoutubeAudienceDemographics.objects.create(
            channel=self.channel,
            age_group='age18-24',
            gender='female',
            viewer_percentage=45.5
        )
        YoutubeAudienceDemographics.objects.create(
            channel=self.channel,
            age_group='age25-34',
            gender='male',
            viewer_percentage=35.0
        )

    # Создаем фиктивный объект Credentials
    def mock_credentials_from_info(*args, **kwargs):
        mock_creds = MagicMock(spec=GoogleCredentialsClass) 
        mock_creds.valid = True
        mock_creds.expired = False
        mock_creds.universe_domain = 'googleapis.com'
        mock_creds.token = kwargs.get('info', {}).get('token')
        mock_creds.refresh_token = kwargs.get('info', {}).get('refresh_token')
        mock_creds.token_uri = kwargs.get('info', {}).get('token_uri')
        mock_creds.client_id = kwargs.get('info', {}).get('client_id')
        mock_creds.client_secret = kwargs.get('info', {}).get('client_secret')
        mock_creds.scopes = kwargs.get('info', {}).get('scopes')
        return mock_creds

    # Мокируем функцию get_youtube_service из services.py
    def mock_get_youtube_service(*args, **kwargs):
        mock_service = MagicMock()
        mock_service.channels.return_value.list.return_value.execute.return_value = {
            'items': [{'id': 'UC_test_channel_id'}]
        }
        return mock_service

    # Мокируем функцию get_youtube_analytics_service из services.py
    def mock_get_youtube_analytics_service(*args, **kwargs):
        mock_service = MagicMock()
        
        # Mock для первого вызова (основные метрики)
        mock_service.reports.return_value.query.return_value.execute.side_effect = [
            # Ответ для views, subscribersGained, subscribersLost
            {
                'rows': [
                    ['2025-08-17', 100, 5, 1],
                    ['2025-08-16', 101, 6, 1],
                ]
            },
            # Ответ для viewerPercentage
            {
                'rows': [
                    ['age18-24', 'female', 45.5],
                    ['age25-34', 'male', 35.0],
                ]
            }
        ]
        return mock_service

    # Мокируем функции обновления данных, чтобы они не делали ничего
    def mock_update_services(*args, **kwargs):
        pass

    @patch('google.oauth2.credentials.Credentials.from_authorized_user_info', side_effect=mock_credentials_from_info)
    @patch('youtube.services.get_youtube_service', side_effect=mock_get_youtube_service)
    @patch('youtube.services.get_youtube_analytics_service', side_effect=mock_get_youtube_analytics_service)
    @patch('youtube.services.update_all_videos', side_effect=mock_update_services)
    def test_youtube_dashboard_view_success(self, mock_update_videos, mock_get_analytics, mock_get_youtube, mock_creds_info):
        """Проверка, что страница дашборда загружается корректно для авторизованного пользователя."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('youtube-dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'youtube/dashboard.html')
        self.assertIn('channel_title', response.context)
        self.assertIn('channel_id', response.context)
        
    def test_unauthenticated_api_access(self):
        """Проверка, что неаутентифицированные пользователи не могут получить доступ к API."""
        response = self.client.get(reverse('channel_trends'))
        self.assertEqual(response.status_code, 302)
        
        response = self.client.get(reverse('video_trends'))
        self.assertEqual(response.status_code, 302)
        
    def test_channel_trends_api_view_success(self):
        """Проверка, что API трендов канала возвращает корректные данные."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('channel_trends'), {'channel_id': self.channel.channel_id})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('dates', data)
        self.assertIn('views', data)
        self.assertIn('subscribers_gained', data)
        self.assertEqual(len(data['dates']), 5)

    def test_channel_trends_api_view_no_channel_id(self):
        """Проверка, что API возвращает ошибку, если нет channel_id."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('channel_trends'))
        self.assertEqual(response.status_code, 200)

    def test_video_trends_api_view_success(self):
        """Проверка, что API трендов видео возвращает корректные данные."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('video_trends'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('videos', data)
        self.assertEqual(len(data['videos']), 3)
        
    def test_audience_demographics_api_view_success(self):
        """Проверка, что API демографии возвращает корректные данные."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('audience_demographics'), {'channel_id': self.channel.channel_id})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('demographics', data)
        self.assertIn('age_groups', data['demographics'])
        self.assertIn('genders', data['demographics'])
        self.assertEqual(len(data['demographics']['age_groups']), 2)
        self.assertEqual(len(data['demographics']['genders']), 2)
        
    def test_audience_demographics_api_view_no_channel_id(self):
        """Проверка, что API демографии возвращает 400, если нет channel_id."""
        response = self.client.get(reverse('audience_demographics'))
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['error'], 'Channel ID is required')
        
    def test_audience_demographics_api_view_nonexistent_channel(self):
        """Проверка, что API демографии возвращает 404 для несуществующего канала."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('audience_demographics'), {'channel_id': 'non_existent_id'})
        self.assertEqual(response.status_code, 404)
        
    @patch('youtube.views.fetch_viewer_activity')    
    def test_viewer_activity_api_view_success(self, mock_fetch):
        """
        Проверка, что API активности аудитории возвращает корректные данные.
        """
        self.client.force_login(self.user)
        mock_fetch.return_value = {
            'device_type': [['Desktop', 1000], ['Mobile', 500]],
            'subscribed_status': [['SUBSCRIBED', 800], ['UNSUBSCRIBED', 200]]
        }
        
        url = reverse('viewer_activity')
        response = self.client.get(url, {
            'date_from': '2025-07-18',
            'date_to': '2025-08-17',
            'channel_id': self.channel.channel_id
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['device_type'], [['Desktop', 1000], ['Mobile', 500]])
        self.assertEqual(response.json()['subscribed_status'][0][0], 'SUBSCRIBED')
        
    def test_viewer_activity_api_view_missing_dates(self):
        """
        Проверка, что API возвращает 400, если отсутствуют даты.
        """
        self.client.force_login(self.user)
        url = reverse('viewer_activity')
        response = self.client.get(url, {'channel_id': self.channel.channel_id})
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('start_date and end_date are required', response.json()['error'])
        
    def test_viewer_activity_api_view_unauthenticated(self):
        """
        Проверка, что неаутентифицированные пользователи не могут получить доступ.
        """
        response = self.client.get(reverse('viewer_activity'))
        
        self.assertEqual(response.status_code, 302) 
        
    def test_viewer_activity_api_view_no_credentials(self):
        """
        Проверка, что API возвращает 401, если у пользователя нет credentials.
        """
        no_creds_user = CustomUser.objects.create_user(email='nocreds@example.com', password='password')
        self.client.force_login(no_creds_user)
        
        url = reverse('viewer_activity')
        response = self.client.get(url, {
            'date_from': '2025-07-18',
            'date_to': '2025-08-17',
            'channel_id': self.channel.channel_id
        })
        
        self.assertEqual(response.status_code, 401)
        self.assertIn('No credentials found for this user', response.json()['error'])
        
    @patch('youtube.views.fetch_viewer_activity')
    def test_viewer_activity_api_view_no_channel(self, mock_fetch):
        """
        Проверка, что API возвращает 404, если у пользователя нет канала.
        """
        no_channel_user = CustomUser.objects.create_user(email='nochannel@example.com', password='password')
        GoogleCredentials.objects.create(
            user=no_channel_user,
            access_token='fake_access_token',
            refresh_token='fake_refresh_token',
            token_expiry=timezone.now() + timedelta(hours=1),
            scopes=' '.join(settings.YOUTUBE_SCOPES),
            client_id=settings.YOUTUBE_CLIENT_ID,
            client_secret=settings.YOUTUBE_CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token",
        )
        self.client.force_login(no_channel_user)
        
        url = reverse('viewer_activity')
        response = self.client.get(url, {
            'date_from': '2025-07-18',
            'date_to': '2025-08-17'
        })
        
        self.assertEqual(response.status_code, 404)
        self.assertIn('No channels found for this user', response.json()['error'])    