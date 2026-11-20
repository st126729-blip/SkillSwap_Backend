from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import VouchViewSet, ReputationSummaryView

router = DefaultRouter()
router.register('vouches', VouchViewSet, basename='vouch')

urlpatterns = router.urls + [
    path('reputation/<int:user_id>/', ReputationSummaryView.as_view(), name='reputation_summary'),
]