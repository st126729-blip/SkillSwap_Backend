from django.urls import path

from . import views

app_name = "ps4"

urlpatterns = [
    path("", views.index, name="index"),
    path("persona/<slug:slug>/", views.persona, name="persona"),
    path("persona/<slug:slug>/scenario/", views.scenario, name="scenario"),
    path("findings/", views.findings, name="findings"),
    path("requirements/", views.requirements, name="requirements"),
    path("mvp/", views.mvp, name="mvp"),
]
