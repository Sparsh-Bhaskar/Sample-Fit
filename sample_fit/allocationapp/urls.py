from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),                    # Homepage with allocation & logs preview
    path('logs/', views.logs_view, name='logs'),          # Filterable logs page
    path('download-logs/', views.download_logs, name='download_logs'),  # Excel download of logs
]
