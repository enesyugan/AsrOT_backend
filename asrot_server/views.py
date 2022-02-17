from rest_framework.views import APIView
from rest_framework import serializers as rf_serializers
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from pathlib import Path
from datetime import datetime
import os

from users.models import CustomUser
from . import models
from . import services
from . import selectors
from AsrOT import settings, sec_settings

base_data_path_unk = sec_settings.base_data_path_unk
base_data_path = sec_settings.base_data_path
server_base_path = sec_settings.server_base_path


class SetVttCorrectionApi(APIView):
    permission_classes = [IsAuthenticated]

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
                correct_vtt_path = correct_vtt_path + "/{}.vtt".format(task_instance.audio_filename)  
            
        print("SetVTT: {} ".format(task_id))
        if correct_vtt_path == None:
            print("Vtt not found using name: {}".format(serializer.validated_data.get('vtt_name', 'unk')))
            correct_vtt_path = base_data_path_unk + str(request.user) + "/origin_unknown"
            if not os.path.exists(correct_vtt_path):
                os.makedirs(correct_vtt_path)
            correct_vtt_path = correct_vtt_path + "/" + serializer.validated_data.get('vtt_name', 'unk') + "_correction{}.vtt".format(datetime.now().strftime("%Y_%m_%d_%H_%M_%S"))
        print("Uploading corrected vtt: {}".format(correct_vtt_path))
        services.vtt_set(correct_vtt_path, vtt_data, request.user, task_instance)
        return Response({}, status=status.HTTP_200_OK)
        

### Every user can ask with his token other peoples tasks
## check if task with task_id exists for user than return (ist es sein task)
class GetTaskStatusApi(APIView):
    permission_classes = [IsAuthenticated]
    
    class InputSerializer(rf_serializers.Serializer):
        taskId = rf_serializers.CharField(required=True)

    class OutputSerializer(rf_serializers.Serializer):
        status = rf_serializers.CharField(max_length=1000)

    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        model = models.TranscriptionTask.objects.filter(task_id=serializer.validated_data['taskId']).last()
        if model == None:
            return Response({'error': "No file with given taskId was saved to database"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        t_status = model.status
        out_data={}
        out_data['status'] = t_status
        out_serializer = self.OutputSerializer(data=out_data)
        out_serializer.is_valid(True)
        return Response({'status': out_serializer.data}, status=status.HTTP_200_OK)

class GetTasksApi(APIView):
    permission_classes = [IsAuthenticated]

    class OutputSerializer(rf_serializers.Serializer):
        user = CustomUser
        task_id = rf_serializers.CharField(max_length=500)
        file_size = rf_serializers.IntegerField()
        task_name = rf_serializers.CharField(max_length=500)
        audio_filename = rf_serializers.CharField(max_length=1000)
        data_path = rf_serializers.CharField(max_length=1000)
        status = rf_serializers.CharField(max_length=500)
        date_time = rf_serializers.DateTimeField()
        language = rf_serializers.CharField(max_length=500)

    def get(self, request):
        tasks = selectors.task_list(filters={'user':request.user})
        out_serializer = self.OutputSerializer(tasks, many=True)
        return Response({"tasks": out_serializer.data}, status=status.HTTP_200_OK)

class GetTextApi(APIView):
    permission_classes = [IsAuthenticated]

    class InputSerializer(rf_serializers.Serializer):
        taskId = rf_serializers.CharField(required=True)

    class OutputSerializer(rf_serializers.Serializer):
        text = rf_serializers.CharField()
        audio_filename = rf_serializers.CharField()

    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        model = models.TranscriptionTask.objects.filter(task_id=serializer.validated_data['taskId']).last()
        if model == None:
            return Response({'error': "There is no task with given taskId."} \
				, status=status.HTTP_503_SERVICE_UNAVAILABLE) 
        transcriptionHypo = model.text_hypo

        if not transcriptionHypo:
            return Response({'error': "There is no text file related to the given taskId. The task may still be in progress"} \
				, status=status.HTTP_503_SERVICE_UNAVAILABLE) 

        encoding = model.encoding
        try:
            text_file = [line.decode(encoding) for line in open(transcriptionHypo, 'rb').readlines()]
        except Exception as e:
            print("GET TEXT ERROR: {}".format(e))
            return Response({'error': "Failed to decode text file. There seems to be a encoding mismatch."} \
				, status=status.HTTP_503_SERVICE_UNAVAILABLE) 
            
        print(text_file)
        text_file = "".join(text_file)
        file_name = Path(transcriptionHypo).stem
        out_data={}
        out_data['audio_filename'] = file_name
        out_data['text'] = text_file
        out_serializer = self.OutputSerializer(data=out_data)
        out_serializer.is_valid(True)
        return Response(out_serializer.data, status=status.HTTP_200_OK)
        


### Every user can ask with his token other peoples tasks
## check if task with task_id exists for user than return (ist es sein task)

class GetVttApi(APIView):
    permission_classes = [IsAuthenticated]

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
        transcriptionHypo = model.transcription_hypo
        if not transcriptionHypo:
            return Response({'error': "There is no vtt file related to the given taskId. The task may still be in progress"} \
				, status=status.HTTP_503_SERVICE_UNAVAILABLE) 

        encoding = model.encoding
        try:
            vtt_file = [line.decode(encoding) for line in open(transcriptionHypo, 'rb').readlines()]
        except Exception as e:
            print("GET VTT ERROR: {}".format(e))
            return Response({'error': "Failed to decode vtt file. There seems to be a encoding mismatch."} \
				, status=status.HTTP_503_SERVICE_UNAVAILABLE) 
            

        vtt_file = "".join(vtt_file)
        file_name = Path(transcriptionHypo).stem
        out_data={}
        out_data['vtt'] = vtt_file
        out_serializer = self.OutputSerializer(data=out_data)
        out_serializer.is_valid(True)
        return Response(out_serializer.data, status=status.HTTP_200_OK)

        #response = HttpResponse(FileWrapper(vtt_file), content_type='application/txt')
        #response['Content-Disposition'] = 'attachment; filename="%s"' % file_name
        #return response



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
        

