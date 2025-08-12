from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import RegisterSerializer, LoginSerializer, LogoutSerializer
import requests
from django.views import View
from django.conf import settings
from django.shortcuts import redirect, render
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.contrib.auth import get_user_model, authenticate, login
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.utils import timezone
from datetime import timedelta
from accounts.models import GoogleCredentials
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

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


class LoginPageView(View):
    def get(self, request):
        return render(request, 'user_auth/login.html')

    def post(self, request):
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next') or '/'
            return redirect(next_url)
        else:
            return render(request, 'user_auth/login.html', {'form': None, 'errors': True})
        
        
class LogoutView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refresh_token = serializer.validated_data["refresh"]
        try:
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
        return Response({'error': 'Failed to get token', 'details': token_resp.json()}, status=400)

    token_json = token_resp.json()
    id_token_str = token_json.get('id_token')
    refresh_token_value = token_json.get('refresh_token')
    access_token_value = token_json.get('access_token')
    expires_in = token_json.get('expires_in', 3600)

    if not id_token_str:
        return Response({'error': 'No id_token in token response'}, status=400)

    try:
        id_info = id_token.verify_oauth2_token(id_token_str, google_requests.Request(), settings.GOOGLE_CLIENT_ID)
    except ValueError:
        return Response({'error': 'Invalid id_token'}, status=400)

    email = id_info.get('email')
    name = id_info.get('name', '')

    if not email:
        return Response({'error': 'Email not found in token'}, status=400)

    user, created = User.objects.get_or_create(email=email, defaults={'full_name': name})

    # save or update GoogleCredentials
    if refresh_token_value:  # refresh_token only 1st user accept
        GoogleCredentials.objects.update_or_create(
            user=user,
            defaults={
                'access_token': access_token_value,
                'refresh_token': refresh_token_value,
                'token_expiry': timezone.now() + timedelta(seconds=expires_in),
                'token_uri': token_url,
                'client_id': settings.GOOGLE_CLIENT_ID,
                'client_secret': settings.GOOGLE_CLIENT_SECRET,
                'scopes': settings.GOOGLE_SCOPES,
            }
        )
    else:
        # if refresh_token no, update only access_token & expiry, if GoogleCredentials 
        creds = getattr(user, 'google_credentials', None)
        if creds:
            creds.access_token = access_token_value
            creds.token_expiry = timezone.now() + timedelta(seconds=expires_in)
            creds.save()

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



class ProtectedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"message": "Access granted"})