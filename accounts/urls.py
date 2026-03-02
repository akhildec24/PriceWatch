from django.urls import path

from .views import RegisterView, login_view, logout_view, settings_view

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('settings/', settings_view, name='account_settings'),
]
