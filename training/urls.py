from django.urls import path
from . import views

app_name = 'training'
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('documents/', views.document_list, name='document_list'),
    path('reports/', views.report_index, name='report_index'),
    path('reports/documents/<int:pk>/', views.document_missing_report, name='document_missing_report'),
    path('reports/events/<int:pk>/', views.event_missing_report, name='event_missing_report'),
    path('reports/<str:target_type>/<int:pk>/ignore/<int:employee_id>/', views.ignore_missing, name='ignore_missing'),
    path('reports/<str:target_type>/<int:pk>/download/<str:status>/', views.download_socialization_report, name='download_socialization_report'),
    path('documents/upload/', views.document_upload, name='document_upload'),
    path('mandiri/', views.independent_start, name='independent_start'),
    path('mandiri/<int:pk>/', views.read_document, name='read_document'),
    path('mandiri/<int:pk>/selesai/', views.complete_reading, name='complete_reading'),
    path('events/', views.event_list, name='event_list'),
    path('events/create/', views.event_create, name='event_create'),
    path('events/<int:pk>/', views.event_detail, name='event_detail'),
    path('events/<int:pk>/hadir/', views.attend_event, name='attend_event'),
    path('users/upload/', views.upload_users, name='upload_users'),
]
