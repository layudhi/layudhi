from django.urls import path
from . import views

app_name = 'training'
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('documents/', views.document_list, name='document_list'),
    path('documents/upload/', views.document_upload, name='document_upload'),
    path('mandiri/', views.independent_start, name='independent_start'),
    path('mandiri/<int:pk>/', views.read_document, name='read_document'),
    path('mandiri/<int:pk>/selesai/', views.complete_reading, name='complete_reading'),
    path('events/', views.event_list, name='event_list'),
    path('events/create/', views.event_create, name='event_create'),
    path('users/upload/', views.upload_users, name='upload_users'),
]
