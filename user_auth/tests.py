from django.test import TestCase, Client
from django.urls import reverse
from rest_framework import status
from accounts.models import CustomUser

class AuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_email = 'testuser@example.com'
        self.user = CustomUser.objects.create(email=self.user_email, full_name="Test User")

        self.protected_url = reverse('protected_view')

    def test_protected_endpoint_requires_auth(self):
        """Доступ к защищённому эндпоинту без логина должен возвращать 403"""
        response = self.client.get(self.protected_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_protected_endpoint_with_login(self):
        """Доступ к защищённому эндпоинту после логина должен быть разрешён"""
        self.client.force_login(self.user)  
        response = self.client.get(self.protected_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.json())
        self.assertEqual(response.json()['message'], 'Access granted')
