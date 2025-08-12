from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse

class GoogleOAuthTests(TestCase):

    @patch('youtube.services.requests.get')
    @patch('youtube.services.requests.post')
    def test_google_callback_success(self, mock_post, mock_get):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'access_token': 'fake-access-token',
            'refresh_token': 'fake-refresh-token',
            'expires_in': 3600,
        }
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            'email': 'testuser@example.com',
            'name': 'Test User',
        }

        url = reverse('youtube-callback')
        response = self.client.get(url, {'code': 'fakecode'})

        self.assertEqual(response.status_code, 302)  # redirect after success

