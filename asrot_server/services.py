from rest_framework import serializers as rf_serializers

from users.models import CustomUser
from . import models
from . import selectors
from . import workers
from . import worker_process as worker
from utils import get_segments
from AsrOT import sec_settings

import os
import tempfile
import subprocess
from datetime import datetime, timedelta
import asyncio
import sys


base_path = sec_settings.server_base_path

def vtt_set(file_path, vtt_data, user, task_instance=None):
    with open(file_path, "wb") as f:
        f.write(vtt_data.encode('utf-8'))
    if user.id == None:
        user = selectors.get_user_list(filters={'email': "unkown@unkown.com"}).last()
    print(f"services: vtt_set: {user}")
    model = models.TranscriptionCorrection(task_id=task_instance,
                                    user=user,
                                    transcription_correction=file_path)    
    
    try:
        model.full_clean()
    except Exception as e:
        raise rf_serializers.ValidationError(e)
    model.save()


def segment_audio(audio, name):
    err={}
    try:
        with tempfile.NamedTemporaryFile(mode='w+b', suffix='.wav') as sourcefile, \
            tempfile.NamedTemporaryFile(mode='r+', suffix='.seg') as resultfile:

            sourcefile.write(audio)

            #command = ['./worker_scripts/segment_audio.sh', sourcefile.name, resultfile.name, name]
            command = ['{}/worker_scripts/segment_audio.sh'.format(base_path), sourcefile.name, resultfile.name, name]

            #p = subprocess.run(command, text=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p = subprocess.run(command, text=True, encoding='utf-8',  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
           # p = subprocess.Popen(command, text=True, encoding='utf-8',  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            #for line in p.stderr:
            #    print(line)

            return (resultfile.read(), '---STDOUT---\n' + p.stdout + '\n---STDERR---\n' + p.stderr, err )
    except Exception as e:
        err['segmentation'] = str(e)
        return ("ERROR", '---STDOUT---\n \n---STDERR---\n',err )

def format_seg_as_stm(segmentation):

    #TODO is sorting really necessary or is seg already in order


    dic = {}
    for line in segmentation.splitlines():
        name0, name1, start_str, end_str = line.split()
        start = float(start_str)
        end = float(end_str)
        dic[start] = f'{name0}-{int(start*100):07}_{int(end*100):07} {name1} {start:.2f} {end:.2f}\n'

    result = [ line for _, line in sorted(dic.items()) ]

    return ''.join(result)

def stm_to_vtt_time(time):
    td = timedelta( seconds=round(float(time), 3) )
    #dummy date, important is the time 00:00:00.000000
    time = datetime(1970, 1, 1)
    #we need the datetime, since time + timedelta isn't supported
    time += td
    time = time.time()
    return time.isoformat('milliseconds')


def set_to_vtt(text, task_id):
    result = f'WEBVTT \n\nNOTE task_id: {task_id}\n\n'
    log = ""
    for line in text.splitlines():
        line = line.strip()
        try:
            start, end, *hypo = line.split()
        except ValueError:
            log += f'badly formatted line {line}'
            continue
        hypo = ' '.join(hypo)
        start = stm_to_vtt_time(start)
        end = stm_to_vtt_time(end)
        result += f"{start} --> {end} \n"
        result += hypo + "\n\n"

    return result, log

def write_log(logFile, log, err=""):
    with open(logFile, "w") as logfile:
        logfile.write(log)
        logfile.write("\n\n====\n====\n\n")
        logfile.write(err)


#def pipe(*, serializer: rf_serializers.Serializer, user: CustomUser, uid, audio_filename, data_path, date_time, audio_bytes):
def pipe(data):
        serializer = data['serializer']
        user = data['user']
        uid = data['uid']
        audio_filename = data['audio_filename']
        data_path = data['data_path']
        log_dir = data['log_dir']
        date_time = data['date_time']
        audio_bytes = data['audio_bytes']
        file_size = data['file_size']
        print("past validation")
        #result_dir = data_path + "/results"
        #log_dir = data_path + "/logs"
       # if not os.path.exists(result_dir):
       #     os.makedirs(result_dir)
       # if not os.path.exists(log_dir):
       #     os.makedirs(log_dir)
        ## result paths
        segmentation_path = data_path + "/seg/{}.seg".format(audio_filename)
        txt_path= data_path + "/txt/{}.txt".format(audio_filename)
        hypo_vtt_path = data_path + "/hypo-vtt/{}.vtt".format(audio_filename)        
        ## log paths
        conversion_log = log_dir + "/conversion.log"
        seg_log = log_dir + "/segmentation.log"
        asr_log = log_dir + "/asr.log"
        vtt_log = log_dir + "/vtt.log"
        ##
        if "de" == serializer.validated_data['sourceLanguage']:
            encoding = 'latin-1'
        else:
            encoding = 'utf-8'
       
        new_model = models.TranscriptionTask(task_id=uid,
                                        user=user,
                                        task_name=serializer.validated_data['taskName'],
					file_size=file_size,
                                        audio_filename=audio_filename,
                                        data_path=data_path,
                                        status="segmentation",
                                        date_time=date_time,
                                        language=serializer.validated_data['sourceLanguage'],
					encoding=encoding)
        try:
            new_model.full_clean()
        except Exception as e:
            raise rf_serializers.ValidationError(e)
        new_model.save()
        
        new_model = models.TranscriptionTask.objects.filter(task_id=uid).last()


        #Segmentation
        print(len(audio_bytes))
        print(audio_filename)
        #segmentation, log, exceptions = segment_audio(audio_bytes, audio_filename)
        exceptions = None
        segmentation = get_segments(audio_bytes, audio_filename)

        #print("seg: {}".format(segmentation))
        if exceptions:
            print(exceptions)
            err = ""
            for key, value in exceptions.items():
                err += "{} : {} \n".format(key,value)
            print("Pipe failed: {}".format(err))
            print(err)
            write_log(conversion_log, log, err)
            new_model.status = 'failed'
            try:
                new_model.full_clean()
            except Exception as e:
                raise rf_serializers.ValidationError(e)
            return
            #raise rf_serializers.ValidationError(exceptions)
            #return Response(exceptions, status=status.HTTP_400_BAD_REQUEST)

        with open(segmentation_path,"w") as seg_file:
            seg_file.write(segmentation)
        
        print('Segmentation done')
        #new_model = models.TranscriptionTask.objects.filter(task_id=uid).last()
        new_model.status = "stm"
        try:
            new_model.full_clean()
        except Exception as e:
            raise rf_serializers.ValidationError(e)
        new_model.save()

        new_model = models.TranscriptionTask.objects.filter(task_id=uid).last()
        #ToSTM
        segmentation = format_seg_as_stm(segmentation)
        with open(segmentation_path, "w") as stm_file:
            stm_file.write(segmentation)

        print('STM Done')
       # new_model = models.TranscriptionTask.objects.filter(task_id=uid).last()
        new_model.status = "transcription"
        try:
            new_model.full_clean()
        except Exception as e:
            raise rf_serializers.ValidationError(e)

        new_model.save()
        new_model = models.TranscriptionTask.objects.filter(task_id=uid).last()
      			
        #ASR
        try:
            text, log, *additional = workers.asr_worker(audio_bytes, segmentation, serializer.validated_data['sourceLanguage'])
            text = text.strip()
        except Exception as e:
            print("Pipe failed: {}".format(e))
            new_model.status = 'failed'
            try:
                new_model.full_clean()
            except Exception as e:
                raise rf_serializers.ValidationError(e)

            new_model.save()
            return
        print(sys.getdefaultencoding())           
        text_hypo = ""
        for line in text.split('\n'):
            text_hypo += " ".join(line.split()[2:])
            text_hypo += "\n"

        try:
            with open(txt_path, "wb") as txt_file:
                txt_file.write(text_hypo.encode(encoding))
            write_log(asr_log, log)
        except Exception as e:
            print("Pipe failed: {}".format(e))            
            new_model.status = 'failed'
            try:
                new_model.full_clean()
            except Exception as e:
                raise rf_serializers.ValidationError(e)

            new_model.save()
            returna
        new_model.text_hypo = txt_path
        try:
            new_model.full_clean()
        except Exception as e:
            raise rf_serializers.ValidationError(e)

        new_model.save()
        new_model = models.TranscriptionTask.objects.filter(task_id=uid).last()

        print("Transcription saved")
    #    full_zip.writestr(f'{subtask.title}/{subtask.title}.txt', text)
     #   print('ASR done')
        #ToVtt
        try:
            vtt, log = set_to_vtt(text, uid)           
            with open(hypo_vtt_path, "wb") as vtt_file:
                vtt_file.write(vtt.encode(encoding))
            write_log(vtt_log, log)


        #    full_zip.writestr(f'{subtask.title}/{subtask.title}.vtt', vtt)
        except Exception as e:
            print("Pipe failed: {}".format(e))                        
            new_model.status = 'failed'
            try:
                new_model.full_clean()
            except Exception as e:
                raise rf_serializers.ValidationError(e)

            new_model.save()
            return
           # log_zip.writestr('text_to_vtt.log', traceback.format_exc())
        print('Vtt done')
        #new_model = models.TranscriptionTask.objects.filter(task_id=uid).last()
        new_model.status = "done"
        new_model.transcription_hypo = hypo_vtt_path
        try:
            new_model.full_clean()
        except Exception as e:
            raise rf_serializers.ValidationError(e)

        new_model.save()
        return



