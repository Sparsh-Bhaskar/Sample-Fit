from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('allocationapp.urls')),  # Change 'allocationapp' to your app name
]
