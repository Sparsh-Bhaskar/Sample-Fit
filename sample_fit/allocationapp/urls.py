from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),                    # Homepage with allocation & logs preview
    path('logs/', views.logs_view, name='logs'),          # Filterable logs page
    path('download-logs/', views.download_logs, name='download_logs'),  # Excel download of logs
    path("request-correction/", views.request_sample_correction, name="request_sample_correction"),
    path("verify-correction-otp/", views.verify_correction_otp, name="verify_correction_otp"),
]
