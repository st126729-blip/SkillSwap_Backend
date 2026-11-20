from rest_framework.routers import DefaultRouter
from .views import BuildLogEntryViewSet

router = DefaultRouter()
router.register('build-logs', BuildLogEntryViewSet, basename='buildlog')

urlpatterns = router.urls