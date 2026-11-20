from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView

from projects.views import ProjectViewSet, MilestoneViewSet
from trades.views import TradeViewSet
from wallet.views import MyWalletView, MyLedgerView
from suggestions.views import suggestions

from django.conf import settings
from django.conf.urls.static import static

router = DefaultRouter()
router.register('projects', ProjectViewSet, basename='project')
router.register('milestones', MilestoneViewSet, basename='milestone')
router.register('trades', TradeViewSet, basename='trade')


class ThrottledTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'token'


urlpatterns = [
    path('admin/', admin.site.urls),
    path('ps4/', include('ps4.urls')),
    path('api/', include(router.urls)),
    path('api/', include('feed.urls')),
    path('api/', include('buildlogs.urls')),
    path('api/', include('groups.urls')),
    path('api/', include('reputation.urls')),
    path('api/wallet/', MyWalletView.as_view()),
    path('api/ledger/', MyLedgerView.as_view()),
    path('api/', include('accounts.urls')),
    path("api/", include("messaging.urls")),
    path('api/token/', ThrottledTokenObtainPairView.as_view()),
    path('api/suggestions/', suggestions),
    path('api/token/refresh/', TokenRefreshView.as_view()),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)