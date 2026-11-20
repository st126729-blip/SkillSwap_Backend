from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='api_register'),
    path('verify-email/', views.VerifyEmailView.as_view(), name='api_verify_email'),
    path('resend-code/', views.ResendCodeView.as_view(), name='api_resend_code'),
    path('login/', views.LoginView.as_view(), name='api_login'),
    path('logout/', views.LogoutView.as_view(), name='api_logout'),
    path('me/', views.MeView.as_view(), name='api_me'),
    path('users/<str:username>/', views.UserProfileView.as_view(), name='api_user_profile'),
    path('users/', views.UserSearchView.as_view(), name='api_user_search'),
    path('forgot-password/', views.ForgotPasswordView.as_view(), name='api_forgot_password'),
    path('verify-reset-code/', views.VerifyResetCodeView.as_view(), name='api_verify_reset_code'),
    path('reset-password/', views.ResetPasswordView.as_view(), name='api_reset_password'),
]