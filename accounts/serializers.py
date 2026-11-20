from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import Profile

ALLOWED_EMAIL_DOMAINS = ['gmail.com', 'ait.asia']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_staff']


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_email(self, value):
        email = value.lower()
        domain = email.split('@')[-1]
        if domain not in ALLOWED_EMAIL_DOMAINS:
            raise serializers.ValidationError(
                f"Email must end with @{' or @'.join(ALLOWED_EMAIL_DOMAINS)}."
            )
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("This email is already registered.")
        return email

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value


class VerifyCodeSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    code = serializers.CharField(max_length=6)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


# ---- Quên mật khẩu ----

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class VerifyResetCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True)


# ---- Hồ sơ ----

def _project_lists(user):
    from projects.models import Project  # import trong hàm để tránh import vòng
    cols = ['id', 'title', 'description', 'status']
    owned = Project.objects.filter(owner=user)
    collaborating = Project.objects.filter(collaborator=user)
    return list(owned.values(*cols)), list(collaborating.values(*cols))


class PublicProfileSerializer(serializers.ModelSerializer):
    """Hồ sơ công khai, không có email."""
    username = serializers.CharField(source='user.username', read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    owned_projects = serializers.SerializerMethodField()
    collaborating_projects = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'username', 'date_joined', 'bio',
            'github_url', 'figma_url', 'behance_url', 'is_verified',
            'owned_projects', 'collaborating_projects',
        ]
        read_only_fields = fields

    def get_owned_projects(self, profile):
        return _project_lists(profile.user)[0]

    def get_collaborating_projects(self, profile):
        return _project_lists(profile.user)[1]


class OwnProfileSerializer(PublicProfileSerializer):
    """Dùng cho /me/. Vẫn trả id, username, email, is_staff như UserSerializer cũ
    nên AuthContext không bị ảnh hưởng. Chỉ bio và 3 link là sửa được."""
    id = serializers.IntegerField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    is_staff = serializers.BooleanField(source='user.is_staff', read_only=True)

    class Meta(PublicProfileSerializer.Meta):
        fields = ['id', 'email', 'is_staff'] + PublicProfileSerializer.Meta.fields
        read_only_fields = [
            'id', 'email', 'is_staff', 'username', 'date_joined', 'is_verified',
            'owned_projects', 'collaborating_projects',
        ]