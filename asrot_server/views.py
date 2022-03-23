from rest_framework.views import APIView
from rest_framework import serializers as rf_serializers
from rest_framework.response import Response
from rest_framework import status, pagination
from rest_framework.permissions import IsAuthenticated

from wsgiref.util import FileWrapper

from django import http
from django.http import StreamingHttpResponse

import pathlib
from datetime import datetime
import os
import wave
import uuid
import sys
import requests
import glob
import re
import mimetypes

from users.models import CustomUser
from users.permissions import CanMakeAssignments
from . import models
from . import services
from . import selectors
from AsrOT import settings, sec_settings

base_data_path_unk = sec_settings.base_data_path_unk
base_data_path = sec_settings.base_data_path
server_base_path = sec_settings.server_base_path


class GetCorrectedVttApi(APIView):
    #permission_classes = [IsAuthenticated]

    class InputSerializer(rf_serializers.Serializer):
        taskId = rf_serializers.CharField(required=True)

        def validate_taskId(self, value):
            if not models.TranscriptionTask.objects.filter(task_id=value).exists():
                raise rf_serializers.ValidationError({'taskId': 'Must point to a valid task iD'})
            return value


    class OutputSerializer(rf_serializers.Serializer):
        vtt = rf_serializers.CharField()
 

    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ## TODO should be in selectors.py
        task = models.TranscriptionTask.objects.get(task_id=serializer.validated_data['taskId'])
        
        if not task.corrections.all().exists():
            return Response({'error': "No corrected file for given task"}, status=status.HTTP_404_NOT_FOUND)

        ## TODO should be in selectors.py 
        correction = task.corrections.all().order_by('-last_commit').first()

        out_serializer = self.OutputSerializer(instance=correction)
        return Response(out_serializer.data, status=status.HTTP_200_OK)


### Every user can ask with his token other peoples tasks
## check if task with task_id exists for user than return (ist es sein task)
class GetTaskApi(APIView):
 
    class OutputSerializer(rf_serializers.Serializer):
        user = CustomUser
        task_id = rf_serializers.UUIDField()
        file_size = rf_serializers.IntegerField(source='audio_filesize')
        task_name = rf_serializers.CharField()
        audio_filename = rf_serializers.CharField()
        date_time = rf_serializers.DateTimeField()
        language = rf_serializers.CharField()
        correction = rf_serializers.SerializerMethodField()
        status = rf_serializers.CharField()
        assigned = rf_serializers.BooleanField()
        corrected = rf_serializers.BooleanField()

        def get_correction(self, task):
            correction = selectors.correction_list(filters={'task_id': task})
            return True if correction else False

    def get(self, request):
        task_id = request.query_params.get('taskId')
        task = selectors.task_list(filters={'task_id':task_id}).last()
        if not task:
            return Response({'error': "There is no task with given taskId."} \
                                , status=status.HTTP_404_NOT_FOUND)

        out_serializer = self.OutputSerializer(instance=task)
        return Response({"tasks": out_serializer.data}, status=status.HTTP_200_OK)

    

class SetVttCorrectionApi(APIView):
    #permission_classes = [IsAuthenticated]

    class InputSerializer(rf_serializers.Serializer):
        vtt = rf_serializers.CharField(required=True)
        task_id = rf_serializers.UUIDField(required=False, default=None)
        vtt_name = rf_serializers.CharField(required=False, max_length=500, default='unk')

        def validate_task_id(self, value):
            if value is None:
                return value
            if not models.TranscriptionTask.objects.filter(task_id=value).exists():
                raise rf_serializers.ValidationError({'task_id': 'Must point to a valid task iD'})
            return value


    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        correction = services.create_vtt_correction(
            user=request.user,
            vtt_data=serializer.validated_data['vtt'],
            task_id=serializer.validated_data['task_id'],
            vtt_name=serializer.validated_data['vtt_name'],
        )

        return Response({}, status=status.HTTP_200_OK)

     

### Every user can ask with his token other peoples tasks
## check if task with task_id exists for user than return (ist es sein task)
class GetTaskStatusApi(APIView):
    permission_classes = [IsAuthenticated]
    
    class InputSerializer(rf_serializers.Serializer):
        taskId = rf_serializers.UUIDField(required=True)

        def validate_taskId(self, value):
            if not models.TranscriptionTask.objects.filter(task_id=value).exists():
                raise rf_serializers.ValidationError({'taskId': 'Must point to a valid task iD'})
            return value


    class OutputSerializer(rf_serializers.Serializer):
        status = rf_serializers.CharField()


    #TODO this should be a GET request, with the id passed in either the URL or the query_params
    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = models.TranscriptionTask.objects.get(task_id=serializer.validated_data['taskId'])

        out_serializer = self.OutputSerializer(instance=task)
        return Response(out_serializer.data, status=status.HTTP_200_OK)



class GetTasksApi(APIView):
    permission_classes = [IsAuthenticated]

    class OutputSerializer(rf_serializers.Serializer):
        user = CustomUser
        task_id = rf_serializers.CharField()
        file_size = rf_serializers.IntegerField(source='audio_filesize')
        task_name = rf_serializers.CharField()
        audio_filename = rf_serializers.CharField()
        status = rf_serializers.CharField()
        date_time = rf_serializers.DateTimeField()
        language = rf_serializers.CharField()


    def get(self, request):
        own_tasks = selectors.task_list(filters={'user':request.user})
        own_tasks_ser = self.OutputSerializer(own_tasks, many=True)
        assigned_tasks = selectors.get_assigned_tasks(request.user)
        assigned_tasks_ser = self.OutputSerializer(assigned_tasks, many=True)
        return Response({"tasks": own_tasks_ser.data, 'assignedTasks': assigned_tasks_ser.data}, status=status.HTTP_200_OK)



### Every user can ask with his token other peoples tasks
## check if task with task_id exists for user than return (ist es sein task)
class GetMediaApi(APIView):
    
    class InputSerializer(rf_serializers.Serializer):
        taskId = rf_serializers.CharField(required=True)

        def validate_taskId(self, value):
            if not models.TranscriptionTask.objects.filter(task_id=value).exists():
                raise rf_serializers.ValidationError({'taskId': 'Must point to a valid task iD'})
            return value


    def post(self, request):
        print(request)
        print("-1")
        serializer = self.InputSerializer(data=request.data)
        print("00")
        serializer.is_valid(raise_exception=True)
        print("111")
        task = models.TranscriptionTask.objects.get(task_id=serializer.validated_data['taskId'])
        print("222")
        if not task.media_file:
            return Response({'error': "There is no data_path file related to the given taskId. The task may still be in progress"} \
                                , status=status.HTTP_404_NOT_FOUND)

        file_name = pathlib.PurePath(task.media_file.name)
        
        with task.media_file.open('rb') as file:
            response = http.HttpResponse(file, content_type='video/mp4')
        #print(type(task.media_file))
        #print(str(task.media_file))
        #print(task.media_file.url)
        #chunk_size = request.META.get('HTTP_RANGE', '').strip()
        #print(chunk_size)

        #print(mimetypes.guess_type(str(task.media_file)))
        #print(os.path.getsize(str(task.media_file)))
        #print(type(chunk_size))
        #try:
        #    response = StreamingHttpResponse(FileWrapper(open(str(task.media_file), "rb"), int(chunk_size)),content_type=mimetypes.guess_type(str(task.media_file))[0])
        #    response['Content-Length'] = os.path.getsize(str(task.media_file))
        response['Content-Disposition'] = f'attachment; filename={file_name.stem}.{file_name.suffix}'
        #except Exception as e:
        #    print(e)
        return response



### Every user can ask with his token other peoples tasks
## check if task with task_id exists for user than return (ist es sein task)
class GetTextApi(APIView):
    #permission_classes = [IsAuthenticated]

    class InputSerializer(rf_serializers.Serializer):
        taskId = rf_serializers.CharField(required=True)

        def validate_taskId(self, value):
            if not models.TranscriptionTask.objects.filter(task_id=value).exists():
                raise rf_serializers.ValidationError({'taskId': 'Must point to a valid task iD'})
            return value


    class OutputSerializer(rf_serializers.Serializer):
        text = rf_serializers.CharField()
        audio_filename = rf_serializers.CharField()


    #TODO this should be a GET request, with the id passed in either the URL or the query_params
    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = models.TranscriptionTask.objects.get(task_id=serializer.validated_data['taskId'])

        if not task.txt_file:
            return Response({'error': "There is no text file related to the given taskId. The task may still be in progress"}, 
                            status=status.HTTP_404_NOT_FOUND) 

        out_serializer = self.OutputSerializer(instance=task)
        return Response(out_serializer.data, status=status.HTTP_200_OK)
        


### Every user can ask with his token other peoples tasks
## check if task with task_id exists for user than return (ist es sein task)
class GetVttApi(APIView):
    #permission_classes = [IsAuthenticated]

    class InputSerializer(rf_serializers.Serializer):
        taskId = rf_serializers.CharField(required=True)

        def validate_taskId(self, value):
            if not models.TranscriptionTask.objects.filter(task_id=value).exists():
                raise rf_serializers.ValidationError({'taskId': 'Must point to a valid task iD'})
            return value


    class OutputSerializer(rf_serializers.Serializer):
        vtt = rf_serializers.CharField()
 

    #TODO this should be a GET request, with the id passed in either the URL or the query_params
    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ## should be in selectors.py
        task = models.TranscriptionTask.objects.get(task_id=serializer.validated_data['taskId'])
        if not task.vtt_file:
            return Response({'error': "There is no vtt file related to the given taskId. The task may still be in progress"}, 
                            status=status.HTTP_404_NOT_FOUND) 

        out_serializer = self.OutputSerializer(instance=task)
        return Response(out_serializer.data, status=status.HTTP_200_OK)



class CreateTaskApi(APIView):
    permission_classes = [IsAuthenticated]

    class InputSerializer(rf_serializers.Serializer):
        taskName = rf_serializers.CharField(required=True)
        audioFile = rf_serializers.FileField(required=True)
        sourceLanguage = rf_serializers.CharField(max_length=500, required=True)
        #translationLanguage = rf_serializers.CharField(max_length=500, required=False)

        def validate_sourceLanguage(self, value):
            if not value in settings.languages_supported:
                raise rf_serializers.ValidationError({"sourceLanguage": "You need to define one of the valid languages {}"\
						.format(settings.languages_supported)})
            return value


    def post(self, request):

        print(request.is_secure())     

        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task = services.create_task(
            task_name=serializer.validated_data['taskName'],
            user=request.user,
            audiofile=serializer.validated_data['audioFile'],
            language=serializer.validated_data['sourceLanguage']
        )
        
        return Response({'taskId': task.task_id}, status=status.HTTP_200_OK)
        


class CreateCorrectionClipView(APIView):
    permission_classes = [IsAuthenticated]

    class InputSerializer(rf_serializers.Serializer):
        taskID = rf_serializers.UUIDField()
        commandClip = rf_serializers.FileField()

        originalText = rf_serializers.CharField()
        correctedText = rf_serializers.CharField()
        prevContext = rf_serializers.CharField(allow_blank=True)
        succContext = rf_serializers.CharField(allow_blank=True)

        beginContext = rf_serializers.TimeField()
        beginText = rf_serializers.TimeField()
        endText = rf_serializers.TimeField()
        endContext = rf_serializers.TimeField()

        def validate_taskID(self, value):
            if not models.TranscriptionTask.objects.filter(task_id=value).exists():
                raise rf_serializers.ValidationError({'taskID': 'Must point to a valid task iD'})
            return value

  
    def post(self, request, *args, **kwargs):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        clip = services.create_correction_clip(
            user=request.user,
            task_id=serializer.validated_data['taskID'],
            audio=serializer.validated_data['commandClip'],
            original_text=serializer.validated_data['originalText'],
            corrected_text=serializer.validated_data['correctedText'],
            context_before=serializer.validated_data['prevContext'],
            context_after=serializer.validated_data['succContext'],
            context_start=serializer.validated_data['beginContext'],
            text_start=serializer.validated_data['beginText'],
            text_end=serializer.validated_data['endText'],
            context_end=serializer.validated_data['endContext'],
        )
        return Response({}, status=status.HTTP_201_CREATED)



class GetAllTasksView(APIView):
    permission_classes = [IsAuthenticated, CanMakeAssignments]

    class FilterSerializer(rf_serializers.Serializer):
        name = rf_serializers.CharField(required=False, default='')

    class OutputSerializer(rf_serializers.Serializer):
        user = rf_serializers.EmailField(source='user.email')
        task_id = rf_serializers.CharField()
        file_size = rf_serializers.IntegerField(source='audio_filesize')
        task_name = rf_serializers.CharField()
        audio_filename = rf_serializers.CharField()
        status = rf_serializers.CharField()
        date_time = rf_serializers.DateTimeField()
        language = rf_serializers.CharField()

    #TODO configure default paginator in settings and switch to generic view
    class Paginator(pagination.PageNumberPagination):
        page_size = 100
        page_query_param = 'page'
        page_size_query_param = 'items_per_page'

    def get(self, request, *args, **kwargs):
        filter_ser = self.FilterSerializer(data=request.query_params)
        filter_ser.is_valid(raise_exception=True)

        queryset = selectors.task_list(filters={
            'task_name__startswith': filter_ser.validated_data['name'],
        }).order_by('-date_time')

        paginator = self.Paginator()
        page = paginator.paginate_queryset(queryset, request, self)
        serializer = self.OutputSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)



class CreateAssignmentView(APIView):
    permission_classes = [IsAuthenticated, CanMakeAssignments]

    class InputSerializer(rf_serializers.Serializer):
        email = rf_serializers.EmailField()
        taskID = rf_serializers.UUIDField()

        def validate_email(self, value):
            if not selectors.get_user_list(filters={'email':value}).exists():
                raise rf_serializers.ValidationError({'email':"Must be a valid user's email"})
            return value

        def validate_taskID(self, value):
            if not selectors.task_list(filters={'task_id':value}).exists():
                raise rf_serializers.ValidationError({'taskID':"Must be a valid task's iD"})
            return value


    def post(self, request, *args, **kwargs):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = services.create_single_assignment(
            owner=request.user,
            assignee_email=serializer.validated_data['email'],
            task_id=serializer.validated_data['taskID'],
        )

        return Response({}, status=status.HTTP_201_CREATED)
