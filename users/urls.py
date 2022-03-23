from django.contrib import admin
from django.urls import path

from . import views
from AsrOT import sec_settings

urlpatterns = [
    path(sec_settings.login_api, views.LogInApi.as_view() ),
    path(sec_settings.logout_api, views.LogOutApi.as_view() ),
    path(sec_settings.userinfo_api, views.UserInfoApi.as_view() ),
    path(sec_settings.register_api, views.RegisterUserApi.as_view() ),
    path('listusers/', views.UserListView.as_view(), ),
    path('listlangs/', views.LanguageListView.as_view(), ),
]
