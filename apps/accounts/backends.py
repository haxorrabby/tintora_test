from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameModelBackend(ModelBackend):
    """Authenticate using either email or username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if not username or not password:
            return None

        try:
            user = UserModel.objects.filter(
                Q(email__iexact=username) | Q(username__iexact=username)
            ).first()
        except Exception:
            return None

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
