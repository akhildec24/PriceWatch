from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from accounts.views import dashboard
from trackers.views import (
    AddProductView,
    ProductPreviewView,
    ConfirmTrackingView,
    WatchlistView,
    ProductDetailView,
    DeleteTrackingRuleView,
    UpdateAlertRuleView,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', dashboard, name='dashboard'),

    path('accounts/', include('accounts.urls')),

    path('add/', AddProductView.as_view(), name='add_product'),
    path('preview/', ProductPreviewView.as_view(), name='product_preview'),
    path('confirm/', ConfirmTrackingView.as_view(), name='confirm_tracking'),
    path('watchlist/', WatchlistView.as_view(), name='watchlist'),
    path('product/<int:pk>/', ProductDetailView.as_view(), name='product_detail'),
    path('tracking/<int:pk>/delete/', DeleteTrackingRuleView.as_view(), name='delete_tracking'),
    path('tracking/<int:pk>/alert/', UpdateAlertRuleView.as_view(), name='update_alert'),
]
