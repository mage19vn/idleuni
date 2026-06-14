from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='compiler/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('register/', views.register_view, name='register'),
    path('profile/', views.profile_view, name='profile'),
    path('password/', auth_views.PasswordChangeView.as_view(template_name='compiler/password_change.html', success_url='/profile/'), name='password_change'),
    path('', views.index_view, name='index'),
    path('report.html', views.report_view, name='report'),
    path('api/visualize/', views.visualize_api, name='visualize_api'),
    path('api/task_status/<str:task_id>/', views.task_status_api, name='task_status_api'),
    path('api/save_snippet/', views.save_snippet_api, name='save_snippet_api'),
    path('api/snippets/', views.snippets_api, name='snippets_api'),
    path('api/templates/', views.templates_api, name='templates_api'),
    path('s/<str:hash_id>/', views.view_snippet, name='view_snippet'),
]