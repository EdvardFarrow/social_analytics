from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()

class AuthTests(APITestCase):
    def setUp(self):
        self.register_url = reverse('register')
        self.login_url = reverse('login')
        self.logout_url = reverse('logout')
        self.protected_url = reverse('protected') 

        self.user_data = {
        'email': 'testuser@example.com',
        'full_name': 'Test User',
        'password': 'strong_password_123',
        'password2': 'strong_password_123',
    }

    def test_register_user(self):
        response = self.client.post(self.register_url, self.user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email=self.user_data['email']).exists())

    def test_login_user(self):
        User.objects.create_user(email=self.user_data['email'], password=self.user_data['password'])

        response = self.client.post(self.login_url, self.user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.access_token = response.data['access']
        self.refresh_token = response.data['refresh']

    def test_access_protected_endpoint(self):
        # Зарегистрируем и залогинимся, чтобы получить токен
        User.objects.create_user(email=self.user_data['email'], password=self.user_data['password'])
        login_resp = self.client.post(self.login_url, self.user_data, format='json')
        access = login_resp.data['access']
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)

        # Попытка без токена
        response = self.client.get(self.protected_url)
        print('Response status without token:', response.status_code)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # С токеном
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        response = self.client.get(self.protected_url)
        print('Response status with token:', response.status_code)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout(self):
        # Создаем пользователя и получаем токены
        User.objects.create_user(email=self.user_data['email'], password=self.user_data['password'])
        login_resp = self.client.post(self.login_url, self.user_data, format='json')
        refresh = login_resp.data['refresh']
        access = login_resp.data['access']

        # Добавляем access токен в заголовок
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        # Логаут с refresh токеном в теле
        response = self.client.post(self.logout_url, {'refresh': refresh}, format='json')
        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)
