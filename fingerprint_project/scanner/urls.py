# scanner/urls.py
from django.urls import path
from .views import capture_fingerprint

urlpatterns = [
    path('capture/', capture_fingerprint, name='capture_fingerprint'),
]
