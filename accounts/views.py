from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.exceptions import TokenError
from decimal import Decimal

from .serializers import (
    UserSerializer, RegisterSerializer, VerifyCodeSerializer, LoginSerializer,
    OwnProfileSerializer, PublicProfileSerializer,
    ForgotPasswordSerializer, VerifyResetCodeSerializer, ResetPasswordSerializer,
)
from .models import EmailVerification, Profile, PasswordResetCode
from wallet.models import Wallet, add_credit

SIGNUP_BONUS_AMOUNT = Decimal('20')  # answers "where do credits initially come from?"


def issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {'access': str(refresh.access_token), 'refresh': str(refresh)}


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'register'

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.create_user(
            username=serializer.validated_data['username'],
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password'],
            is_active=False,
        )

        code = EmailVerification.generate_code()
        EmailVerification.objects.create(user=user, code=code)

        try:
            send_mail(
                subject='Your SkillTrade verification code',
                message=f'Your verification code is: {code}\nIt expires in 10 minutes.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )
        except Exception:
            user.delete()  # xóa luôn EmailVerification nhờ cascade (nếu FK on_delete=CASCADE)
            return Response(
                {'detail': 'Could not send verification email. Please try again.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


        return Response(
            {'user_id': user.id, 'email': user.email, 'detail': 'Verification code sent.'},
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data['user_id']
        code = serializer.validated_data['code']

        try:
            user = User.objects.get(id=user_id)
            verification = EmailVerification.objects.get(user=user)
        except (User.DoesNotExist, EmailVerification.DoesNotExist):
            return Response({'detail': 'No pending verification found.'}, status=status.HTTP_400_BAD_REQUEST)

        if verification.is_expired():
            return Response({'detail': 'Code expired. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)

        if verification.code != code:
            return Response({'detail': 'Incorrect code.'}, status=status.HTTP_400_BAD_REQUEST)

        user.is_active = True
        user.save()
        verification.delete()

        # One-time signup bonus, recorded as an ordinary LedgerEntry via add_credit().
        wallet, created = Wallet.objects.get_or_create(user=user)
        if created:
            add_credit(
                wallet, SIGNUP_BONUS_AMOUNT, 'SIGNUP_BONUS',
                reference_id=f"user-{user.pk}",
                note="Welcome bonus granted on email verification.",
            )

        tokens = issue_tokens(user)
        return Response({
            'detail': 'Email verified successfully.',
            'user': UserSerializer(user).data,
            **tokens,
        })


class ResendCodeView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        user_id = request.data.get('user_id')
        try:
            user = User.objects.get(id=user_id, is_active=False)
        except User.DoesNotExist:
            return Response({'detail': 'No pending registration found.'}, status=status.HTTP_400_BAD_REQUEST)

        EmailVerification.objects.filter(user=user).delete()
        code = EmailVerification.generate_code()
        EmailVerification.objects.create(user=user, code=code)

        try:
            send_mail(
                subject='Your SkillTrade verification code (resent)',
                message=f'Your new verification code is: {code}\nIt expires in 10 minutes.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )
        except Exception:
            return Response(
                {'detail': 'Could not send email. Please try again.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({'detail': 'A new code has been sent to your email.'})


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'token'

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        user = authenticate(request, username=username, password=password)

        if user is None:
            # authenticate() also returns None for inactive users, so look the
            # user up separately. Only reveal "not verified" when the password
            # is correct, so nothing leaks to someone guessing accounts.
            candidate = User.objects.filter(username=username).first()
            if candidate and not candidate.is_active and candidate.check_password(password):
                return Response(
                    {'detail': 'This account is not verified yet.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {'detail': 'Invalid username or password.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tokens = issue_tokens(user)
        return Response({'user': UserSerializer(user).data, **tokens})


# ---- Quên mật khẩu ----

def _check_reset_code(email, code):
    """Trả về (user, reset, error_response). Có lỗi thì error_response khác None."""
    bad = Response({'detail': 'Invalid or expired code.'}, status=status.HTTP_400_BAD_REQUEST)
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    reset = getattr(user, 'password_reset', None) if user else None
    if not reset:
        return None, None, bad
    if reset.is_expired():
        reset.delete()
        return None, None, Response({'detail': 'Code expired. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)
    if reset.attempts >= PasswordResetCode.MAX_ATTEMPTS:
        reset.delete()
        return None, None, Response({'detail': 'Too many attempts. Please request a new code.'}, status=status.HTTP_400_BAD_REQUEST)
    if reset.code != code:
        reset.attempts += 1
        reset.save(update_fields=['attempts'])
        return None, None, Response({'detail': 'Incorrect code.'}, status=status.HTTP_400_BAD_REQUEST)
    return user, reset, None


class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'token'

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            PasswordResetCode.objects.filter(user=user).delete()
            code = PasswordResetCode.generate_code()
            PasswordResetCode.objects.create(user=user, code=code)
            send_mail(
                subject='Your SkillTrade password reset code',
                message=f'Your password reset code is: {code}\nIt expires in 10 minutes.\n'
                        f'If you did not request this, ignore this email.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )
        # Luôn trả cùng một câu trả lời để không lộ email nào đã đăng ký
        return Response({'detail': 'If that email is registered, a code has been sent.'})


class VerifyResetCodeView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'token'

    def post(self, request):
        serializer = VerifyResetCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _, _, error = _check_reset_code(
            serializer.validated_data['email'], serializer.validated_data['code'],
        )
        if error:
            return error
        return Response({'detail': 'Code verified.'})  # chưa xóa mã, bước đổi mật khẩu còn cần


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'token'

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user, reset, error = _check_reset_code(data['email'], data['code'])
        if error:
            return error

        try:
            validate_password(data['new_password'], user)
        except DjangoValidationError as e:
            return Response({'new_password': list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(data['new_password'])
        user.save()
        reset.delete()
        return Response({'detail': 'Password updated. You can log in now.'})


# ---- Hồ sơ ----

class MeView(generics.RetrieveUpdateAPIView):
    """GET: hồ sơ của mình (vẫn có id, username, email, is_staff). PATCH: sửa bio + 3 link."""
    serializer_class = OwnProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        return profile


class UserProfileView(generics.RetrieveAPIView):
    """GET /users/<username>/: hồ sơ công khai, không có email."""
    serializer_class = PublicProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        user = get_object_or_404(User, username=self.kwargs['username'], is_active=True)
        profile, _ = Profile.objects.get_or_create(user=user)
        return profile


class UserSearchView(APIView):
    """GET /users/?q=abc: gợi ý user có username chứa 'abc' (không phân biệt hoa thường)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if not q:
            return Response([])
        users = (
            User.objects.filter(is_active=True, username__icontains=q)
            .exclude(pk=request.user.pk)[:30]
        )
        # Tên bắt đầu bằng chữ đã gõ lên trước, sau đó theo bảng chữ cái
        ranked = sorted(
            users,
            key=lambda u: (not u.username.lower().startswith(q.lower()), u.username.lower()),
        )[:8]
        return Response([{'id': u.id, 'username': u.username} for u in ranked])


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'detail': 'Refresh token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response({'detail': 'Invalid or expired token.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_205_RESET_CONTENT)