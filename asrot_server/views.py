from rest_framework.views import APIView
from rest_framework import serializers as rf_serializers
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from django.http import QueryDict
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
from django.shortcuts import render
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.http import HttpResponse
from wsgiref.util import FileWrapper


from pydub import AudioSegment
from pathlib import Path
from datetime import datetime, timedelta
from threading import Thread
from multiprocessing import Process
import numpy as np
import tempfile
import subprocess
import base64
import os
import wave
import uuid
import sys
import requests

#from . import workers
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
        audioFile = rf_serializers.CharField(required=True)
        sourceLanguage = rf_serializers.CharField(max_length=500, required=True)
     #   translationLanguage = rf_serializers.CharField(max_length=500, required=False)


    def convert_to_wav(self, source, ext):
        err={}
        with tempfile.NamedTemporaryFile(mode='w+b', suffix=ext) as sourcefile, \
		tempfile.NamedTemporaryFile(mode='r+b', suffix='.wav') as resultfile:

            sourcefile.write(source)

            command = ['ffmpeg', '-nostdin', '-y', '-i', sourcefile.name, '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', resultfile.name]
            p = subprocess.run(command, text=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            data_byte=resultfile.read()
            try:
                sound = AudioSegment.from_wav(resultfile)
                sound = sound.set_frame_rate(16000)
                data_ = np.fromstring(sound._data, np.int16)
                data_ = base64.b64encode(data_)
            except Exception as e:
                #logger.error("STT error reading file: {}".format(e))
                print("error: {}".format(e))
                err['media processing'] = str(e)
                data_ = bytearray("error")

            return (data_.decode('latin-1'), data_byte, '---STDOUT---\n' + p.stdout + '\n---STDERR---\n' + p.stderr, err )

    def write_log(self, logFile, log, err=""):
        with open(logFile, "w") as logfile:
            logfile.write(log)
            logfile.write("\n\n====\n====\n\n")            
            logfile.write(err)
            

    def post(self, request):

        data = request.data
       # data_path = base_data_path + str(request.user)
        data_path = base_data_path 
        print(data_path)
        if not 'sourceLanguage' in data or not data['sourceLanguage'] in settings.languages_supported:
            raise rf_serializers.ValidationError({"sourceLanguage": "You need to define one of the valid languages {}"\
						.format(settings.languages_supported)})        
        if not 'taskName' in data or not data['taskName']:
            raise rf_serializers.ValidationError({"taskName": "You need define a task name"})        
            
 #       logger.info("request is secure: {}".format(request.is_secure()))
        print(request.is_secure())
        
        try:
            data['audioFile']
        except Exception as e:
            raise rf_serializers.ValidationError({"audioFile": "A media file needs to be send"})        

        if not isinstance(data, QueryDict):
            tmp = data
            data = QueryDict('', mutable=True)
            data.update(tmp)

        if isinstance(data['audioFile'], (bytes, bytearray)):
            audio = data['audioFile'].decode('latin-1')
            data['audioFile'] = audio

        else:
            uploaded_file = data['audioFile']
           # logger.info("File content_type: {}".format(uploaded_file.content_type))
           # logger.info("File contentt_type.split(/): {}".format(uploaded_file.content_type.split('/')[0]))
           # logger.info("uploaded_file.name: {}".format(uploaded_file.name))

           # print("File content_type: {}".format(uploaded_file.content_type))
           # print("File contentt_type.split(/): {}".format(uploaded_file.content_type.split('/')[0]))
           # print("uploaded_file.name: {}".format(uploaded_file.name))
           # print(uploaded_file.size)
            ext = Path(uploaded_file.name).suffix
            file_name = Path(uploaded_file.name).stem
            file_name = file_name.replace('/','_').replace('\\','_')
            now = datetime.now()
            date_time = now.strftime("%Y_%m_%d_%H_%M_%S")
            file_name = "{}-{}".format(file_name, date_time)
           # data_path = data_path + "/" + file_name + "_" + date_time
            data_path = data_path + "/" + data['sourceLanguage'].upper() + "/datoid" 
            print(data_path)
            #result_dir = data_path + "/results"            
            wav_dir = data_path + "/wav"
            log_dir = data_path + "/log/{}".format(file_name)

            uid = uuid.uuid4()
            file_sizemb = (uploaded_file.size // 1000000)
            print("File size: {} mb".format(file_sizemb))
            print(request.user)
            print(request.user.restricted_account)
            if request.user.restricted_account:
                if file_sizemb > 10:
                    raise rf_serializers.ValidationError({"file size": "You have a restricted account. Your media file must be smaller than 10 mb. Please write an email to administrators to allow for unlimited upload size."})                  

            if isinstance(data['audioFile'], InMemoryUploadedFile):
                audio = (uploaded_file.file).getvalue()
            if isinstance(data['audioFile'], TemporaryUploadedFile):
                uploaded_file.seek(0)
                audio = uploaded_file.read()

            audio_str, audio_bytes, log, pydub_err = self.convert_to_wav(audio, ext)
            #session = requests.Session()
            #responseTest = requests.post('http://i13hpc29.ira.uka.de:8080/ai_worker/ar_asr', data= dict(audio_bytes=audio_bytes))
            #print(responseTest)
            #print(responseTest.json())
            #print(type(responseTest.json()))
            #print(responseTest.json()['transcription'])
            #print("99999999")
            if not os.path.exists(wav_dir):
                os.makedirs(wav_dir)
            if not os.path.exists(data_path + "/seg"):
                os.makedirs(data_path + "/seg")
            if not os.path.exists(data_path + "/txt"):
                os.makedirs(data_path + "/txt")
            if not os.path.exists(data_path + "/hypo-vtt"):
                os.makedirs(data_path + "/hypo-vtt")
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            conversion_log = log_dir + "/conversion.log"

            if pydub_err:
                err = ""
                for key, value in pydub_err.items():
                    err += "{} : {} \n".format(key,value)
                self.write_log(conversion_log, log, err)
                return Response(pydub_err, status=status.HTTP_400_BAD_REQUEST)

            wav_path = wav_dir+"/{}.wav".format(file_name)
            obj = wave.open(wav_path,'wb')
            obj.setnchannels(1)
            obj.setsampwidth(2)
            obj.setframerate(16000)
            obj.writeframesraw(base64.b64decode(audio_str.strip()))
            obj.close()
            print("Wav of original media file saved to: {}".format(wav_path))
            data['audioFile'] = audio_str
            print("nach data")
       # else:
       #    # print(data['audioFile'][0:300])
       #     data__ = data['audioFile'].encode('latin-1')
       #     print(type(data__))
       #    # print(data__[0:300])
       #     print(type(data['audioFile']))

        serializer = self.InputSerializer(data=data)
        print("nach serializer")
        serializer.is_valid(raise_exception=True)
        print("serializer is valid")
        serializer.validated_data['sourceLanguage'] = serializer.validated_data['sourceLanguage'].lower()
        print("nach langguag set")
        date_time = now.strftime('%Y-%m-%d %H:%M:%S')
        #services.pipe(serializer=serializer, user=request.user, uid=uid, audio_filename=file_name, data_path=data_path, date_time=now.strftime("%Y-%m-%d %H:%M:%S"), audio_bytes=audio_bytes)
        service_data = {"serializer":serializer, 
			"user": request.user,
			"uid": uid,
			"file_size": uploaded_file.size,
			"audio_filename": file_name,
			"data_path": data_path,
			"log_dir": log_dir,
			"date_time": date_time, 
			"audio_bytes": audio_bytes}
        print("for process")
        #p = Process(target=services.pipe, args=(service_data,))
        thread = Thread(target =services.pipe, args=(service_data,))
        thread.start()
        print(sys.version)
        print(sys.path)
        print(sys.version_info)
        print("process definede")
       # try:
        #    p.start()
        #except Exception as e:
        #    print(e)
        print("process started")
        return Response({'taskId': uid}, status=status.HTTP_200_OK)
        

