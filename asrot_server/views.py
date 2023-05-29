from rest_framework.views import APIView
from rest_framework import serializers as rf_serializers
from rest_framework.response import Response
from rest_framework import status, pagination
from rest_framework.permissions import IsAuthenticated

from wsgiref.util import FileWrapper

from django import http
from django.http import StreamingHttpResponse
from django.core.exceptions import ObjectDoesNotExist

import pathlib
#from datetime import datetime
import datetime
from django.utils import timezone
import os
import wave
import uuid
import sys
import requests
import glob
import re
import mimetypes
import shutil

from users.models import CustomUser
from users.permissions import CanMakeAssignments
from . import models
from . import services
from . import selectors
from . import utils
import csv
from AsrOT import settings, sec_settings

base_data_path_unk = sec_settings.base_data_path_unk
base_data_path = sec_settings.base_data_path
server_base_path = sec_settings.server_base_path

class GetMediaHashApi(APIView):
    permission_classes = [IsAuthenticated]

    class InputSerializer(rf_serializers.Serializer):
        mediaName = rf_serializers.CharField(required=True)
        mediaSize = rf_serializers.CharField(required=True)

    class OutputSerializer(rf_serializers.Serializer):
        mediaHash = rf_serializers.CharField()

    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        hash_string = serializer.validated_data["mediaName"]+serializer.validated_data["mediaSize"]
        mediaHash = utils.encrypt_data(hash_string)
        
        out_serializer = self.OutputSerializer(instance={"mediaHash": mediaHash})
        return Response(out_serializer.data, status=status.HTTP_200_OK)
        


class GetListenerApi(APIView):
    permission_classes = [IsAuthenticated]
    
    class InputSerializer(rf_serializers.Serializer):
        taskId = rf_serializers.CharField(required=True)
        userId = rf_serializers.CharField(required=True)

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

        queryset =  models.TranscriptionCorrection.objects.select_related('user','task').filter(finished=True, user_id=serializer.validated_data['userId'], task_id=serializer.validated_data['taskId'])


        if not queryset:
            print("GetListenerApi")
            if not task.vtt_file:
                return Response({'error': "There is no vtt file related to the given taskId: {} and userId: {}".format(serializer.validated_data['taskId'], serializer.validated_data['userId'])},
                        status=status.HTTP_404_NOT_FOUND)
            #hier ist der Fall das es nur ein finshed gibt hier noch mal queryset anlegen ohne den finished filter, dann noch mal prüfen ob 
            #queryset wenn nicht die instanz returnen ansonsten den '-last_commit'
            out_serializer = self.OutputSerializer(instance=task)
            return Response(out_serializer.data, status=status.HTTP_200_OK)

        correction = queryset.order_by('-last_commit').first()

        out_serializer = self.OutputSerializer(instance=correction)
        return Response(out_serializer.data, status=status.HTTP_200_OK)

class GetCorrectedListApi(APIView):
    permission_classes = [IsAuthenticated]

    class OutputSerializer(rf_serializers.Serializer):
        task_user = rf_serializers.EmailField(source='task.user.email')
        corrected_user = rf_serializers.EmailField(source='user.email')
        date_transcribed = rf_serializers.DateTimeField(source='task.date_time')
        date_corrected = rf_serializers.DateTimeField(source='last_commit')
        language = rf_serializers.CharField(max_length=500, source='task.language')
        finished = rf_serializers.BooleanField()        
        task_name = rf_serializers.CharField(max_length=500, source='task.task_name')
        id = rf_serializers.UUIDField( source="task.task_id" )
        corrected_user_id = rf_serializers.CharField(source='user.id')

    
    class Paginator(pagination.PageNumberPagination):
        page_size = 100
        page_query_param = 'page'
        page_size_query_param = 'items_per_page'

    def get(self, request, *args, **kwargs):
        if not request.user.can_make_assignments:
            raise rf_serializers.ValidationError({'error':"No Permission"})
            

        queryset =  models.TranscriptionCorrection.objects.select_related('user','task').filter(finished=True)
        paginator = self.Paginator()        
        page = paginator.paginate_queryset(queryset, request, self)     
        serializer = self.OutputSerializer(page, many=True)      
 
        #return paginator.get_paginated_response(serializer.data)
        return Response(serializer.data, status=status.HTTP_200_OK)

class GetCSVLinksApi(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        print("GetCSVLinksApi")
        response = http.HttpResponse(
        content_type='text/csv',
        )
        response['Content-Disposition'] = 'attachment; filename="ShareYourMedia.csv"'

        try:
            own_tasks = selectors.task_list(filters={'user':request.user})
            writer = csv.writer(response)#, delimiter="\t")
        except Exception as e:
            print(e)

        writer.writerow(['Name', 'Date', 'Share Link'])
        if len(own_tasks) < 1:
            writer.writerow(["You have not generated any transcription yet"])
        for task in own_tasks:
            writer.writerow([str(task.task_name), task.date_time, f"https://transcriptions.dataforlearningmachines.com/shared?task_id={task.task_id}"])

        return response


class PostSelfAssignTaskApi(APIView):
    permission_classes = [IsAuthenticated]
    
    class InputSerializer(rf_serializers.Serializer):
        taskId = rf_serializers.CharField(required=True)

        def validate_taskId(self, value):
            if not models.TranscriptionTask.objects.filter(task_id=value).exists():
                raise rf_serializers.ValidationError({'taskId': 'Must point to a valid task iD'})
            return value

    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task_id = serializer.validated_data['taskId']
      
        res = services.selfassign_task(taskId)
        if not res:       
            raise rf_serializers.ValidationError({'error': 'Couldnt assign task'})
        return Response({}, status=status.HTTP_200_OK)

class GetMediaUrlApi(APIView):
    
    class InputSerializer(rf_serializers.Serializer):
        taskId = rf_serializers.CharField(required=True)

        def validate_taskId(self, value):
            if not models.TranscriptionTask.objects.filter(task_id=value).exists():
                raise rf_serializers.ValidationError({'taskId': 'Must point to a valid task iD'})
            return value

    class OutputSerializer(rf_serializers.Serializer):
        mediaUrl = rf_serializers.CharField()

    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task_id = serializer.validated_data['taskId']

        task = selectors.path_get(filters={'task_id':task_id})
        if not task:
            return Response({'error': "There is no task with given taskId."} \
                                , status=status.HTTP_404_NOT_FOUND) 
        mediaPath = str(task.media_file)

        #mediaUrl = "https://i13hpc29.ira.uka.de/media/" + str(mediaPath.split("media/")[-1])
        mediaUrl = sec_settings.media_url + str(mediaPath.split("media/")[-1])
        body = {}
        body['mediaUrl'] = mediaUrl

        out_serializer = self.OutputSerializer(instance=body)
        return Response(out_serializer.data, status=status.HTTP_200_OK)

class GetCorrectedVttApi(APIView):
    #permission_classes = [IsAuthenticated]

    class InputSerializer(rf_serializers.Serializer):
        taskId = rf_serializers.CharField(required=True)
        original = rf_serializers.BooleanField(default=False)

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
        print("11")
        if not task.corrections.all().filter(**{'user':request.user}).exists() or serializer.validated_data['original']:
            print("222")
            if not task.vtt_file:
                return Response({'error': "There is no vtt file related to the given taskId. The task may still be in progress"},
                        status=status.HTTP_404_NOT_FOUND)
            print("222.5555")
            out_serializer = self.OutputSerializer(instance=task)
            return Response(out_serializer.data, status=status.HTTP_200_OK)

            #return Response({'error': "No corrected file for given task"}, status=status.HTTP_404_NOT_FOUND)
        print("4444")

        ## TODO should be in selectors.py 
        #correction = task.corrections.all().order_by('-last_commit').first()
        correction = task.corrections.all()
        correction =  correction.filter(**{'user':request.user})
        correction = correction.order_by('-last_commit').first()

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
        finished = rf_serializers.BooleanField(default=False)

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
            vtt_data=serializer.validated_data['vtt']+'\n',
            task_id=serializer.validated_data['task_id'],
            vtt_name=serializer.validated_data['vtt_name'],
            finished=serializer.validated_data['finished']
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

class GetVttViaHashApi(APIView):
    permission_classes = [IsAuthenticated]

    class InputSerializer(rf_serializers.Serializer):
        mediaHash = rf_serializers.CharField(required=True)

        def validate_mediaHash(self, value):
            if not models.TranscriptionTask.objects.filter(media_hash=value).exists():
                raise rf_serializers.ValidationError({'mediaHash': 'Must point to a valid hash'})
            return value


    class OutputSerializer(rf_serializers.Serializer):
        vtt = rf_serializers.CharField()
 
    #TODO this should be a GET request, with the id passed in either the URL or the query_params
    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ## should be in selectors.py
        task = models.TranscriptionTask.objects.filter(media_hash=serializer.validated_data['mediaHash']).first()
     
        try:
           if not task.corrections.all().filter(**{'user':request.user}).exists():
               if not task.vtt_file:
                   return Response({'error': "There is no vtt file related to the given taskId. The task may still be in progress"}, 
                               status=status.HTTP_404_NOT_FOUND) 

               out_serializer = self.OutputSerializer(instance=task)

               return Response(out_serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            print("GetVttViaHash Error: {}".format(e))
        ## TODO should be in selectors.py
        #correction = task.corrections.all().order_by('-last_commit').first()
        correction = task.corrections.all()
        correction =  correction.filter(**{'user':request.user})
        correction = correction.order_by('-last_commit').first()

        out_serializer = self.OutputSerializer(instance=correction)
        return Response(out_serializer.data, status=status.HTTP_200_OK)


class DeleteTaskApi(APIView):
    permission_classes = [IsAuthenticated]

    class InputSerializer(rf_serializers.Serializer):
        mediaHash = rf_serializers.CharField(max_length=256, required=True)
    
    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = models.TranscriptionTask.objects.filter(media_hash=serializer.validated_data['mediaHash']).first()
        if task == None: return Response({"error": "This task does not exist"}, status=status.HTTP_404_NOT_FOUND)
        if task.user != request.user:
            return Response({'error': "You can only delete the tasks you created. You did not create the task you want to delete"},
                                status=status.HTTP_404_NOT_FOUND)
        else:
            task_dir = str(os.path.join(pathlib.PurePath(settings.MEDIA_ROOT),task.language.upper(), task.audio_filename))
            print(task_dir)
            if os.path.exists(task_dir):
                shutil.rmtree(task_dir)
            task.delete()
            task = models.TranscriptionTask.objects.filter(media_hash=serializer.validated_data['mediaHash']).first()
            print("does task exists: {}".format(task))

        return Response(status=status.HTTP_200_OK)        


class CheckHashStatusApi(APIView):
    permission_classes = [IsAuthenticated]

    class InputSerializer(rf_serializers.Serializer):
        mediaHash = rf_serializers.CharField(max_length=256, required=True)

    class OutputSerializer(rf_serializers.Serializer):
        exists = rf_serializers.BooleanField()
        status = rf_serializers.CharField()
        task_id = rf_serializers.CharField()
        duration = rf_serializers.CharField()

    def return_nulls(self):
        res={}
        res["exists"] = False
        res["status"] = "NULL"
        res["task_id"] = "NULL"
        res["duration"] = "NULL"
        out_serializer = self.OutputSerializer(instance=res)
        return Response(out_serializer.data, status=status.HTTP_200_OK)   

    def handle_failed_task(self, task):
        task_dir = str(os.path.join(pathlib.PurePath(settings.MEDIA_ROOT),task.language.upper(), task.audio_filename))
        print("Does dir exists: {}\n{}".format(task_dir, os.path.exists(task_dir)))
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir)
        print("deleted dirs")
        task.delete() 
        print("deleted task")

        self.return_nulls()

    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        res = {}
        task = models.TranscriptionTask.objects.filter(media_hash=serializer.validated_data['mediaHash']).first()
        print(task)
        try:
          if task:    
              print("Task status: {}".format(task.status))
              if task.status == "done": 
                res["exists"] = True
                res["status"] = task.status
                res["task_id"] = task.task_id
                res["duration"] = "NULL"
                out_serializer = self.OutputSerializer(instance=res)
                return Response(out_serializer.data, status=status.HTTP_200_OK)
              if task.status == "failed": #or task.status != "done":
                self.handle_failed_task(task)
              res["exists"] = True
              res["status"] = task.status
              res["task_id"] = task.task_id
              with wave.open(task.wav_file, "rb") as wave_file:
                  frame_rate = wave_file.getframerate()
                  nframes = wave_file.getnframes()
              duration = nframes / frame_rate
              current_time = timezone.now()
              time_pased = current_time -task.date_time

              duration_datetime = datetime.timedelta(seconds=duration)
              time_difference =  duration_datetime - time_pased
             # time_difference =  duration_datetime -time_pased
              print("Check Hash Status; how much time left until transcription finished: {}".format(time_difference))

             # if str(time_difference).startswith("-1"):
             #   time_difference =  datetime.timedelta(seconds=duration//2)
             #   print("new dif: {}".format(time_difference))
              if str(time_difference).startswith("-"):
                if task.status != "failed":
                    task.status = "failed"
                    task.full_clean()
                    task.save()
                    res["status"]= "failed"
              str_time_difference = str(time_difference)
              print(str_time_difference)
              str_time_difference = str_time_difference.rsplit('.',1)[0]
              res["duration"] = str_time_difference
              
              out_serializer = self.OutputSerializer(instance=res)
              return Response(out_serializer.data, status=status.HTTP_200_OK)
          else:
              print("CheckHashStatusApi: media with hash: {} not found".format(serializer.validated_data['mediaHash']))
              res["exists"] = False
              res["status"] = "NULL"
              res["task_id"] = "NULL"
              res["duration"] = "NULL"
              out_serializer = self.OutputSerializer(instance=res)
              return Response(out_serializer.data, status=status.HTTP_200_OK)   
        except Exception as e:
            print(e)
        

class CreateTaskApi(APIView):
    permission_classes = [IsAuthenticated]

    class InputSerializer(rf_serializers.Serializer):
        taskName = rf_serializers.CharField(required=True)
        audioFile = rf_serializers.FileField(required=True)
        sourceLanguage = rf_serializers.CharField(max_length=500, required=True)
        mediaHash = rf_serializers.CharField(max_length=256, required=True)
        #translationLanguage = rf_serializers.CharField(max_length=500, required=False)

        def validate_sourceLanguage(self, value):
           # if not value in settings.languages_supported:
            if len(value) >3:
                raise rf_serializers.ValidationError({"sourceLanguage": "You need to define one of the valid languages {}"\
						.format(settings.languages_supported)})
            return value


    def post(self, request):

        print(request.is_secure())     
        print("TEST")
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task = services.create_task(
            task_name=serializer.validated_data['taskName'],
            user=request.user,
            audiofile=serializer.validated_data['audioFile'],
            language=serializer.validated_data['sourceLanguage'],
            media_hash=serializer.validated_data['mediaHash'],
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
        media_hash = rf_serializers.CharField()

    #TODO configure default paginator in settings and switch to generic view
    class Paginator(pagination.PageNumberPagination):
        page_size = 300
        page_query_param = 'page'
        page_size_query_param = 'items_per_page'

    ##Body funktioniert mit get nicht denke ich
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
