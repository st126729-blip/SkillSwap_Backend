from rest_framework.routers import DefaultRouter
from .views import GroupViewSet, GroupPostViewSet

router = DefaultRouter()
router.register('groups', GroupViewSet, basename='group')
router.register('group-posts', GroupPostViewSet, basename='group-post')

urlpatterns = router.urls