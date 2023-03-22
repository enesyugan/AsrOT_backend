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
import hashlib
import time

import requests
import json
from sseclient import SSEClient
from threading import Thread

base_path = sec_settings.server_base_path

mediator_res = list()

def encrypt_data(hash_string):
    sha_signature = hashlib.sha256(hash_string.encode())
    sha_signature = sha_signature.hexdigest()
    return sha_signature


def read_text(sessionID, num_components, mediator_res):
    messages = SSEClient(sec_settings.url + "/ltapi/stream?channel=" + sessionID)
    print("==")
    num_END = 0
    for msg in messages:
        data = json.loads(msg.data)
        mediator_res.append(data)
        if ("controll" in data and data["controll"] == "END"):
            num_END += 1
            if num_END >= num_components:
                break;

def send_start(url, sessionID, streamID, show_on_website, save_path):
    print("Start sending audio")
    data={'controll':"START"}
    if show_on_website:
        data["type"] = "lecture"
        data["name"] = "Audioclient"
    if save_path != "":
        data["directory"] = save_path
    info = requests.post(url + "/ltapi/" + sessionID + "/" + streamID + "/append", json=json.dumps(data))
    if info.status_code != 200:
        print(res.status_code,res.text)
        print("ERROR in starting session")

def send_audio(audio_source, url, sessionID, streamID):
    chunk = audio_source
  #  chunk = audio_source.chunk_modify(chunk)
    if len(chunk) == 0:
        raise KeyboardInterrupt()
    s = time.time()
    e = s + len(chunk)/32000
    print(type(chunk))
    print(type(base64.b64encode(chunk).decode('ascii')))
    data = {"b64_enc_pcm_s16le":base64.b64encode(chunk).decode("ascii"),"start":s,"end":e}
    res = requests.post(url + "/ltapi/" + sessionID + "/" + streamID + "/append", json=json.dumps(data))
    if res.status_code != 200:
        print(res.status_code,res.text)
        print("ERROR in sending audio")
    raise KeyboardInterrupt()

def send_end(url, sessionID, streamID):
    print("Sending END.")
    data={'controll': "END"}
    res = requests.post(url + "/ltapi/" + sessionID + "/" + streamID + "/append", json=json.dumps(data))
    if res.status_code != 200:
        print(res.status_code,res.text)
        print("ERROR in sending END message")
       
                    
def send_session(url, sessionID, streamID, audio_source, show_on_website, upload_video, save_path):
    try:
        send_start(url, sessionID, streamID, show_on_website, save_path)
        if not upload_video:
           # while True:
            send_audio(audio_source, url, sessionID, streamID)
        else:
            #send_video(audio_source.url, url, sessionID, streamID)
            raise KeyboardInterrupt
    except KeyboardInterrupt:
        time.sleep(1)
        send_end(url, sessionID, streamID)

def set_graph(language):
    d = {}
    d["language"] = language
    d["textseg"] = False
    res = requests.post(sec_settings.url + "/ltapi/get_default_asr", json=json.dumps(d))
    if res.status_code != 200:
        print(res.status_code,res.text)
        print("ERROR in requesting default graph for ASR")
    sessionID, streamID = res.text.split()
    graph=json.loads(requests.post(sec_settings.url+"/ltapi/"+sessionID+"/getgraph").text)
    print("Graph:",graph)
    p = dict()
    num_components  = 0
    for sender, reveiver in graph.items():
        if sender.startswith("asr"):
            p[sender] = {}
            p[sender]["version"] = "offline"
            p[sender]["segmenter"] = "SHAS"
            p[sender]["language"] = language
            p[sender]["max_segment_length"] = 15
            p[sender]["min_segment_length"] = 1
            if language == "de":
                p[sender]["asr_server_de"] = "http://192.168.0.60:5008/asr/infer/de,de"
        num_components += 1
    print("NUM comps: {}".format(num_components))
    res = requests.post(sec_settings.url + "/ltapi/" + sessionID + "/setproperties", json=json.dumps(p));
    if res.status_code != 200:
        print(res.status_code,res.text)
        print("ERROR in setting properties")

    return sessionID, streamID, graph, num_components
    

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
        dic[start] = f'{name0} {name1} {start:.2f} {end:.2f}\n'

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
        task.status = "converting"
        task.full_clean()
        task.save()

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

        task.status = "segmenting"
        task.full_clean()
        task.save()

        #Segmentation
        print(len(audio_bytes))
        print(task.audio_filename)

        exceptions = None
        sessionID, streamID, graph, num_components = set_graph(task.language)
        data={'controll':"INFORMATION"}
        info = requests.post(sec_settings.url + "/ltapi/" + sessionID + "/" + streamID + "/append", json=json.dumps(data))
        if info.status_code != 200:
            print(res.status_code,res.text)
            print("ERROR in requesting worker information")
        print("info: {}".format(info))
        t = Thread(target=read_text, args=(sessionID, num_components, mediator_res))
        t.daemon = True
        t.start()
     
        send_session(sec_settings.url, sessionID, streamID, audio_bytes, False, False, "")
        t.join()   
        segmentation = ""
        text_hypo = ""
        s_e_text = ""
        for line in mediator_res:
            print(line)
            print(type(line))
            is_session = line.get("session", None)
            is_controll = line.get("controll", None)
            sender = line.get("sender", None)
            is_sender_asr = False
            if sender == "asr:0":
                is_sender_asr = True
            if is_session and not is_controll and is_sender_asr:
                print(line)
                start = line["start"]
                end = line["end"]
                text = line.get("seq", "None")
                text = text.strip() + "\n"
                text_hypo += text
                s_e_text_line = "{} {} {}".format(start, end, text)
                s_e_text += s_e_text_line
                segmentation += (task.audio_filename+"-%07d_%07d"%(start*100,end*100)+" "+task.audio_filename+" %.2f %.2f"%(start,end)+"\n")

        task.seg_file.save('unused-name', base_files.ContentFile(segmentation))
        
        print('Segmentation done')
        task.status = "stm"
        task.full_clean()
        task.save()
        #ToSTM
        segmentation = format_seg_as_stm(segmentation)
        task.stm_file.save('unused-name', base_files.ContentFile(segmentation))

        print('STM Done')
        task.status = "transcripton"
        task.full_clean()
        task.save()
        

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
            vtt, log = set_to_vtt(s_e_text, task.task_id)           
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


        
