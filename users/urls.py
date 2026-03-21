from django.urls import path,include
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register_user, name="register"),  # user register
    path("user/login/", views.login_user, name="login"),  # user login
    path("logout/", views.logout_user, name="logout"),
    path("user/dashboard/", views.dashboard_user, name="user_dashboard"),
    path(
        "client/register/", views.register_client, name="client_registration"
    ),  # client register
    path("client/login/", views.login_client, name="client_login"),  # client login
    path(
        "client/dashboard/", views.dashboard_client, name="client_dashboard"
    ),  # client dashboard
    # 1. Redirects user TO GitHub
    path("auth/github/", views.github_login, name="github_login"),
    # 2. GitHub redirects back HERE with a code
    path("auth/github/callback/", views.github_callback, name="github_callback"),
    path('identities/', views.identity_list, name='identity_list'),
    path('identities/create/', views.identity_create, name='identity_create'),
    path('identities/<int:name_id>/edit/', views.identity_edit, name='identity_edit'),
    path('identities/<int:name_id>/delete/', views.identity_delete, name='identity_delete'),
    path('search/', views.search_identities, name='search'),
    path('settings/', views.user_settings, name='settings'),
    path("logout/", views.logout_user, name="logout"),
    path('identities/<int:name_id>/access/', views.manage_access, name='manage_access'),
    path('identities/<int:name_id>/access/<int:grant_id>/revoke/', views.revoke_access, name='revoke_access'),
    path("manage/clients/", views.admin_clients, name="admin_clients"),
    path("manage/clients/<int:client_id>/approve/", views.approve_client, name="approve_client"),
    path("manage/clients/<int:client_id>/reject/", views.reject_client, name="reject_client"),
    path("settings/theme/", views.toggle_theme, name="toggle_theme"),
    path("client/theme/", views.toggle_client_theme, name="toggle_client_theme"),
    path("client/logout/", views.client_logout, name="client_logout"),
    path('i18n/', include('django.conf.urls.i18n')),
]
