from rest_framework.views import APIView
from rest_framework import serializers as rf_serializers
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from pathlib import Path
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

    class OutputSerializer(rf_serializers.Serializer):
        vtt = rf_serializers.CharField()
 
    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ## should be in selectors.py
        model = models.TranscriptionTask.objects.filter(task_id=serializer.validated_data['taskId']).last()
        if model == None:
            return Response({'error': "There is no task with given taskId."} \
				, status=status.HTTP_503_SERVICE_UNAVAILABLE)         

        encoding = model.encoding
        data_path = model.data_path
        file_name = model.audio_filename
        print(data_path)
        print(f"{data_path}/correct-vtt/{file_name}")
        corrected_files = glob.glob(os.path.join(data_path, 'correct-vtt', f"{file_name}*"))
        print("2")
        if not corrected_files:
            return Response({'error': "No corrected file for given task"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        print(corrected_files)
        corrected_files.sort(key=os.path.getmtime) 
        print(corrected_files)    
        try:
            vtt_file = [line.decode(encoding) for line in open(corrected_files[-1], 'rb').readlines()]
        except Exception as e:
            print("GET VTT ERROR: {}".format(e))
            return Response({'error': "Failed to decode vtt file. There seems to be a encoding mismatch."} \
				, status=status.HTTP_503_SERVICE_UNAVAILABLE) 
            

        vtt_file = "".join(vtt_file)
        file_name = Path(corrected_files[-1]).stem
        out_data={}
        out_data['vtt'] = vtt_file
        out_serializer = self.OutputSerializer(data=out_data)
        out_serializer.is_valid(True)
        return Response(out_serializer.data, status=status.HTTP_200_OK)



class GetTaskApi(APIView):
 
    class OutputSerializer(rf_serializers.Serializer):
        user = CustomUser
        task_id = rf_serializers.CharField(max_length=500)
        file_size = rf_serializers.IntegerField()
        task_name = rf_serializers.CharField(max_length=500)
        audio_filename = rf_serializers.CharField(max_length=1000)
        date_time = rf_serializers.DateTimeField()
        language = rf_serializers.CharField(max_length=500)   
        correction = rf_serializers.BooleanField()

    def get(self, request):
        task_id = request.query_params.get('taskId')
        task = selectors.task_list(filters={'task_id':task_id}).last()
        if not task:
            return Response({'error': "There is no task with given taskId."} \
                                , status=status.HTTP_503_SERVICE_UNAVAILABLE)

        correction = selectors.correction_list(filters={'task_id': task})
        out_data = {}
        out_data['task_id'] = task.task_id
        out_data['file_size'] = task.file_size
        out_data['audio_filename'] = task.audio_filename
        out_data['task_name'] = task.task_name
        out_data['date_time'] = task.date_time
        out_data['language'] = task.language
        out_data['correction'] = True if correction else False

        out_serializer = self.OutputSerializer(out_data)
        return Response({"tasks": out_serializer.data}, status=status.HTTP_200_OK)

    

class SetVttCorrectionApi(APIView):
    #permission_classes = [IsAuthenticated]

    class InputSerializer(rf_serializers.Serializer):
        vtt = rf_serializers.CharField(required=True)
        task_id = rf_serializers.CharField(required=False, max_length=500)
        vtt_name = rf_serializers.CharField(required=False, max_length=500)

    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        vtt_data = serializer.validated_data['vtt']
        correct_vtt_path = None
        task_instance = None
        task_id = None
        if serializer.validated_data.get('task_id', None) != None:
            task_id = serializer.validated_data['task_id']
        else:
            for line in vtt_data.split('\n'):
                if "NOTE task_id:" in line: 
                    task_id = line.strip().split()[-1]
                    print("TASK ID: {}".format(task_id))
                    break
       
        if task_id != None:
            task_instance = selectors.path_get(filters={'task_id':task_id})#line.strip().split()[-1]
            if task_instance:
                print("VTT found: {}".format(task_instance))
                data_path = task_instance.data_path
                correct_vtt_path = data_path + "/correct-vtt"
                if not os.path.exists(correct_vtt_path):
                    os.makedirs(correct_vtt_path)
                i=0
                while os.path.exists(f"{correct_vtt_path}/{task_instance.audio_filename}_{i}.vtt"):
                    i += 1
                correct_vtt_path = f"{correct_vtt_path}/{task_instance.audio_filename}_{i}.vtt"
                #correct_vtt_path = correct_vtt_path + "/{}.vtt".format(task_instance.audio_filename)  
            
        print("SetVTT: {} ".format(task_id))
        if correct_vtt_path == None:
            print("Vtt not found using name: {}".format(serializer.validated_data.get('vtt_name', 'unk')))
            correct_vtt_path = base_data_path_unk + str(request.user) + "/origin_unknown"
            if not os.path.exists(correct_vtt_path):
                os.makedirs(correct_vtt_path)
            
            correct_vtt_path = correct_vtt_path + "/" + serializer.validated_data.get('vtt_name', 'unk') + "_correction{}.vtt".format(datetime.now().strftime("%Y_%m_%d_%H_%M_%S"))
        print("Uploading corrected vtt: {}".format(correct_vtt_path))
        services.vtt_set(correct_vtt_path, vtt_data,  request.user, task_instance)
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
         
    def post(self, request):
        print(request)
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        model = models.TranscriptionTask.objects.filter(task_id=serializer.validated_data['taskId']).last()

        if model == None:
            return Response({'error': "There is no task with given taskId."} \
                                , status=status.HTTP_503_SERVICE_UNAVAILABLE)
        data_path = model.data_path

        if not data_path:
            return Response({'error': "There is no data_path file related to the given taskId. The task may still be in progress"} \
                                , status=status.HTTP_503_SERVICE_UNAVAILABLE)
        file_name = model.audio_filename
        if not file_name:
            return Response({'error': "No file name for given task"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        media_files = glob.glob(os.path.join(data_path, 'media', f"{file_name}.*"))
        if not media_files:
            return Response({'error': "No file name for given task"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        ext = media_files[0].rsplit('.')[-1]
        file = FileWrapper(open(media_files[0], 'rb'))
        response = HttpResponse(file, content_type='video/mp4')
        response['Content-Disposition'] = f'attachment; filename={file_name}.{ext}'
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