from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
    path('', views.index_view, name='index'),
    path('report.html', views.report_view, name='report'),
    path('api/visualize/', views.visualize_api, name='visualize_api'),
    path('api/task_status/<str:task_id>/', views.task_status_api, name='task_status_api'),
    path('api/save_snippet/', views.save_snippet_api, name='save_snippet_api'),
    path('api/snippets/', views.snippets_api, name='snippets_api'),
    path('api/templates/', views.templates_api, name='templates_api'),
    path('api/keymap/save/', views.save_keymap_api, name='save_keymap_api'),
    path('api/keymap/load/<str:hash_id>/', views.load_keymap_api, name='load_keymap_api'),
    path('s/<str:hash_id>/', views.view_snippet, name='view_snippet'),
]