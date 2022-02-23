from django.urls import path
from django.conf.urls import include

from . import views
from AsrOT import sec_settings


basic_pattern = [
        path(sec_settings.createtask_api, views.CreateTaskApi.as_view() ),
        path(sec_settings.gettasks_api, views.GetTasksApi.as_view(), ),
        path(sec_settings.gettaskstatus_api, views.GetTaskStatusApi.as_view(), ),
        path(sec_settings.getvtt_api, views.GetVttApi.as_view(), ),
        path(sec_settings.gettext_api, views.GetTextApi.as_view(), ), 
        path(sec_settings.setvttcorrection_api, views.SetVttCorrectionApi.as_view(), ),
        path(sec_settings.gettask_api, views.GetTaskApi.as_view(), ),
        path(sec_settings.getmedia_api, views.GetMediaApi.as_view(), ),
        path(sec_settings.getcorrectedvtt_api, views.GetCorrectedVttApi.as_view(), ),
        path('commandclips/', views.CreateCorrectionClipView.as_view(), ),
]

urlpatterns = [
    #path('ping/', views.PingApi.as_view()),
    path('', include((basic_pattern, ''))),
]
