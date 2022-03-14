from rest_framework.views import APIView
from rest_framework import serializers as rf_serializers
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from django import http

import pathlib
from datetime import datetime
import os
import wave
import uuid
import sys
import requests
import glob

from users.models import CustomUser
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
        tasks = selectors.task_list(filters={'user':request.user})
        out_serializer = self.OutputSerializer(tasks, many=True)
        return Response({"tasks": out_serializer.data}, status=status.HTTP_200_OK)



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
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task = models.TranscriptionTask.objects.get(task_id=serializer.validated_data['taskId'])

        if not task.media_file:
            return Response({'error': "There is no data_path file related to the given taskId. The task may still be in progress"} \
                                , status=status.HTTP_404_NOT_FOUND)

        file_name = pathlib.PurePath(task.media_file.name)

        with task.media_file.open('rb') as file:
            response = http.HttpResponse(file, content_type='video/mp4')
        response['Content-Disposition'] = f'attachment; filename={file_name.stem}.{file_name.suffix}'
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
            user=self.request.user,
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
        return Response({}, status=status.HTTP_200_OK)