from django.urls import path
from .views import suggestions

urlpatterns = [path("", suggestions)]