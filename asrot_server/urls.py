from django.urls import path
from django.conf.urls import include

from . import views
from AsrOT import sec_settings
from . import views_default


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
        path(sec_settings.commandclips, views.CreateCorrectionClipView.as_view(), ),
        path(sec_settings.getalltasks, views.GetAllTasksView.as_view(), ),
        path(sec_settings.assigntask, views.CreateAssignmentView.as_view(), ),
        path(sec_settings.getmediaurl, views.GetMediaUrlApi.as_view(), ),
        path(sec_settings.getcsvlink, views.GetCSVLinksApi.as_view(), ),
        path(sec_settings.getcorrectedlist, views.GetCorrectedListApi.as_view(), ),
        path(sec_settings.getlistenertask, views.GetListenerApi.as_view(), ),
        path(sec_settings.getmediahash, views.GetMediaHashApi.as_view(), ),
        path(sec_settings.checkhashstatus, views.CheckHashStatusApi.as_view(), ),
        path(sec_settings.getvttviahash, views.GetVttViaHashApi.as_view(), ),
        path(sec_settings.getalltasksdefault, views_default.GetAllTasksApi.as_view(), ),
        path(sec_settings.settaskhash, views_default.SetTaskHashApi.as_view(), ),
        path(sec_settings.getoriginalmedia, views_default.GetOriginalMediaApi.as_view(), ),
        path(sec_settings.gettasksize, views_default.GetTaskSize.as_view(), ),
        path(sec_settings.deletetask, views.DeleteTaskApi.as_view(), ),
        path(sec_settings.getzip, views.GetZipApi.as_view(), ),
]

urlpatterns = [
    #path('ping/', views.PingApi.as_view()),
    path('', include((basic_pattern, ''))),
] 
