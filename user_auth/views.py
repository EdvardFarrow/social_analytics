from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import RegisterSerializer, LoginSerializer
import requests
from django.conf import settings
from django.shortcuts import redirect
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.contrib.auth import get_user_model

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer

class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer

    def post(self, request):
        user = self.get_serializer(data=request.data)
        user.is_valid(raise_exception=True)
        user = user.validated_data
        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })

class LogoutView(generics.GenericAPIView):
    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception:
            return Response(status=status.HTTP_400_BAD_REQUEST)


User = get_user_model()


api_view(['GET'])
def google_login(request):
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    query_string = "&".join([f"{key}={value}" for key, value in params.items()])
    return redirect(f"{base_url}?{query_string}")


@api_view(['GET'])
def google_callback(request):
    code = request.GET.get('code')
    if not code:
        return Response({'error': 'No code provided'}, status=400)

    token_url = 'https://oauth2.googleapis.com/token'
    token_data = {
        'code': code,
        'client_id': settings.GOOGLE_CLIENT_ID,
        'client_secret': settings.GOOGLE_CLIENT_SECRET,
        'redirect_uri': settings.GOOGLE_REDIRECT_URI,
        'grant_type': 'authorization_code',
    }
    token_resp = requests.post(token_url, data=token_data)
    if token_resp.status_code != 200:
        return Response({'error': 'Failed to get token'}, status=400)
    
    access_token = token_resp.json().get('access_token')

    userinfo_resp = requests.get(
        'https://www.googleapis.com/oauth2/v1/userinfo',
        params={'alt': 'json'},
        headers={'Authorization': f'Bearer {access_token}'},
    )
    if userinfo_resp.status_code != 200:
        return Response({'error': 'Failed to get userinfo'}, status=400)

    user_data = userinfo_resp.json()
    email = user_data.get('email')
    name = user_data.get('name')

    user, created = User.objects.get_or_create(email=email, defaults={'full_name': name})
    
    refresh = RefreshToken.for_user(user)
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': {
            'id': user.id,
            'email': user.email,
            'full_name': user.full_name,  
        }
    })
