from django.core.files import base as base_files

from utils import get_segments
from AsrOT import sec_settings

from pydub import AudioSegment

from . import models, workers

import base64
import tempfile
import subprocess
from datetime import datetime, timedelta
import sys
import numpy as np
import wave

base_path = sec_settings.server_base_path


def convert_to_wav(source, ext):
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


def write_log(lf, log, err=""):
    lf.save('unused-name', base_files.ContentFile(f'{log}\n\n====\n====\n\n{err}'))


def pipe(task: models.TranscriptionTask, audio, file_ext):

        #Conversion
        audio_str, audio_bytes, log, pydub_err = convert_to_wav(audio, file_ext)

        #TODO what is the difference between audio_str and audio_bytes
        #Why save audio_str and use audio_bytes

        if pydub_err:
            err = ""
            for key, value in pydub_err.items():
                err += "{} : {} \n".format(key,value)
            write_log(task.conversion_log, log, err)
            return

        task.wav_file.save('unused-name', base_files.ContentFile(''))
        with task.wav_file.open('wb') as wf:
            with wave.open(wf, 'wb') as wavfile:
                wavfile.setnchannels(1)
                wavfile.setsampwidth(2)
                wavfile.setframerate(16000)
                wavfile.writeframesraw(base64.b64decode(audio_str.strip()))


        #Segmentation
        print(len(audio_bytes))
        print(task.audio_filename)

        exceptions = None
        segmentation = get_segments(audio_bytes, task.audio_filename)

        if exceptions:
            print(exceptions)
            err = ""
            for key, value in exceptions.items():
                err += "{} : {} \n".format(key,value)
            print("Pipe failed: {}".format(err))
            print(err)
            write_log(task.conversion_log, log, err)
            task.status = 'failed'
            task.full_clean()
            return


        task.seg_file.save('unused-name', base_files.ContentFile(segmentation))
        
        print('Segmentation done')
        task.status = "stm"
        task.full_clean()
        task.save()


        #ToSTM
        segmentation = format_seg_as_stm(segmentation)
        task.stm_file.save('unused-name', base_files.ContentFile(segmentation))

        print('STM Done')
        task.status = "transcription"
        task.full_clean()
        task.save()


        #ASR
        try:
            text, log, *additional = workers.asr_worker(audio_bytes, segmentation, task.language)
            text = text.strip()
        except Exception as e:
            print("Pipe failed: {}".format(e))
            task.status = 'failed'
            task.full_clean()
            task.save()
            return
        
        print(sys.getdefaultencoding())           
        text_hypo = ""
        for line in text.split('\n'):
            text_hypo += " ".join(line.split()[2:])
            text_hypo += "\n"

        try:
            task.txt_file.save('unused-name', base_files.ContentFile(text_hypo))
            write_log(task.asr_log, log)
        except Exception as e:
            print("Pipe failed: {}".format(e))            
            task.status = 'failed'
            task.full_clean()
            task.save()
            return

        print("Transcription saved")


        #ToVtt
        try:
            vtt, log = set_to_vtt(text, task.task_id)           
            task.vtt_file.save('unused-name', base_files.ContentFile(vtt))
            write_log(task.vtt_log, log)
        except Exception as e:
            print("Pipe failed: {}".format(e))                        
            task.status = 'failed'
            task.full_clean()
            task.save()
            return

        print('Vtt done')


        task.status = "done"
        task.full_clean()
        task.save()
        return
