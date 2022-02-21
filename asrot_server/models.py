from django.db import models
from django.contrib import auth

import uuid, pathlib, functools


def base_path(instance):
    return pathlib.Path('known')/instance.language.upper()

def upload_data(instance, fn, filetype):
    sub_dir = {
        'wav': 'wav',
        'seg': 'seg',
        'stm': 'seg',
        'txt': 'txt',
        'vtt': 'hypo-vtt',
    }
    return base_path(instance)/sub_dir[filetype]/f'{instance.audio_filename}.{filetype}'

def upload_logs(instance, fn, filetype):
    return base_path(instance)/'log'/instance.audio_filename/f'{filetype}.log'


class TranscriptionTask(models.Model):
    #TODO changing primary key requires resetting database
    task_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False) ## mit uuid ein id generieren dann kann man darüber bspw status abfrage machen
    user = models.ForeignKey(auth.get_user_model(), on_delete=models.CASCADE)
    task_name = models.CharField(max_length=500)
    audio_filename = models.CharField(max_length=1000, null=False)
    audio_filesize = models.IntegerField(null=False)

    status = models.CharField(max_length=500, blank=True) #converting, segmenting,...
    date_time = models.DateTimeField(auto_now_add=True)
    language = models.CharField(max_length=500, null=False)

    #`blank=True` `null=True` since the files are created and saved later in the pipeline
    wav_file = models.FileField(upload_to=functools.partial(upload_data, filetype='wav'), blank=True, null=True)
    seg_file = models.FileField(upload_to=functools.partial(upload_data, filetype='seg'), blank=True, null=True)
    stm_file = models.FileField(upload_to=functools.partial(upload_data, filetype='stm'), blank=True, null=True)
    txt_file = models.FileField(upload_to=functools.partial(upload_data, filetype='txt'), blank=True, null=True)
    vtt_file = models.FileField(upload_to=functools.partial(upload_data, filetype='vtt'), blank=True, null=True)

    conversion_log = models.FileField(upload_to=functools.partial(upload_logs, filetype='conversion'), blank=True, null=True)
    seg_log = models.FileField(upload_to=functools.partial(upload_logs, filetype='segmentation'), blank=True, null=True)
    asr_log = models.FileField(upload_to=functools.partial(upload_logs, filetype='asr'), blank=True, null=True)
    vtt_log = models.FileField(upload_to=functools.partial(upload_logs, filetype='vtt'), blank=True, null=True)

    def __str__(self):
        return str(self.audio_filename) + ' language: ' + str(self.language)

    def clean(self):
        self.language = self.language.lower()



class TranscriptionCorrection(models.Model):
    user = models.ForeignKey(auth.get_user_model(), on_delete=models.CASCADE)
    task_id = models.ForeignKey(TranscriptionTask, on_delete=models.CASCADE, blank=True, null=True)
    transcription_correction = models.CharField(max_length=1000, blank=False)    
    first_commit = models.DateTimeField(auto_now_add=True)
    last_commit = models.DateTimeField(verbose_name='last upload', auto_now=True)
    
    def __str__(self):
        return str(self.user) + 'correction done task_id: ' + str(self.task_id)



def upload_audio(instance, fn):
    path = pathlib.PurePath('audio_clips')/instance.task.task_name/str(instance.user)
    ext = pathlib.PurePath(fn).suffix
    date_string = instance.created.strftime("%Y_%m_%d_%H_%M_%S")
    return path/f'{date_string}{ext}'

class CommandClip(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(auth.get_user_model(), on_delete=models.CASCADE)
    task = models.ForeignKey(TranscriptionTask, on_delete=models.CASCADE)

    audio = models.FileField(upload_to=upload_audio)

    original_text = models.TextField(blank=True)
    corrected_text = models.TextField(blank=True)
    context_before = models.TextField(blank=True)
    context_after = models.TextField(blank=True)

    context_start = models.TimeField()
    text_start = models.TimeField()
    text_end = models.TimeField()
    context_end = models.TimeField()
