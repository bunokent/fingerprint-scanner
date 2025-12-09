# scanner/urls.py
from django.urls import path
from .views import capture_fingerprint
from .views import capture_and_verify

urlpatterns = [
    path('capture/', capture_fingerprint, name='capture_fingerprint'),
    path('verify/', capture_and_verify, name='verify_fingerprint'),

]
