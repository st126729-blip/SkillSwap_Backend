from django.urls import path
from . import views

urlpatterns = [
    path("messages/conversations/", views.conversations),
    path("messages/unread-count/", views.unread_count),
    path("messages/with/<str:username>/", views.thread),
]