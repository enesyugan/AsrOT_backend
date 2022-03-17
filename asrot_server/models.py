import datetime
from django.db import models
from django.contrib import auth
from django.core.files.storage import default_storage

from functools import partial as part
import uuid, pathlib

from AsrOT import sec_settings



def base_path(instance):
    return pathlib.PurePath(sec_settings.base_data_path)/instance.language.upper()



def upload_media(instance, fn):
    filename = pathlib.PurePath(fn)
    return base_path(instance)/'media'/f'{instance.audio_filename}{filename.suffix}'

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
    task_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False) ## mit uuid ein id generieren dann kann man darüber bspw status abfrage machen
    user = models.ForeignKey(auth.get_user_model(), on_delete=models.CASCADE, related_name='owned_tasks')
    task_name = models.CharField(max_length=500)
    audio_filename = models.CharField(max_length=1000, null=False)
    audio_filesize = models.IntegerField(null=False)

    assignees = models.ManyToManyField(auth.get_user_model(), 
        through='TaskAssignment', through_fields=('task', 'assignee'), 
        related_name='assigned_tasks')

    status = models.CharField(max_length=500, blank=True) #converting, segmenting,...
    date_time = models.DateTimeField(auto_now_add=True)
    language = models.CharField(max_length=500, null=False)

    #`blank=True` `null=True` since the files are created and saved later in the pipeline
    media_file = models.FileField(upload_to=upload_media)
    wav_file = models.FileField(upload_to=part(upload_data, filetype='wav'), blank=True, null=True)
    seg_file = models.FileField(upload_to=part(upload_data, filetype='seg'), blank=True, null=True)
    stm_file = models.FileField(upload_to=part(upload_data, filetype='stm'), blank=True, null=True)
    txt_file = models.FileField(upload_to=part(upload_data, filetype='txt'), blank=True, null=True)
    vtt_file = models.FileField(upload_to=part(upload_data, filetype='vtt'), blank=True, null=True)

    conversion_log = models.FileField(upload_to=part(upload_logs, filetype='conversion'), blank=True, null=True)
    seg_log = models.FileField(upload_to=part(upload_logs, filetype='segmentation'), blank=True, null=True)
    asr_log = models.FileField(upload_to=part(upload_logs, filetype='asr'), blank=True, null=True)
    vtt_log = models.FileField(upload_to=part(upload_logs, filetype='vtt'), blank=True, null=True)

    def __str__(self):
        return str(self.audio_filename) + ' language: ' + str(self.language)

    def clean(self):
        self.language = self.language.lower()

    @property
    def text(self):
        with self.txt_file.open('r') as file:
            return file.read()

    @property
    def vtt(self):
        with self.vtt_file.open('r') as file:
            return file.read()



def upload_correction(instance, fn):
    filename = pathlib.PurePath(fn)

    if instance.task != None:
        # Changing the name can't be done in a Storage class, since it should only be used for task-related files
        i = 0
        base_name = base_path(instance.task)/"correct-vtt"
        file_name = base_name/f'{instance.task.audio_filename}__{i:03d}.vtt'
        while default_storage.exists(file_name):
            i += 1
            file_name = base_name/f'{instance.task.audio_filename}__{i:03d}.vtt'
        return str(file_name)     
    else:
        now = datetime.datetime.now()
        return pathlib.PurePath(sec_settings.base_data_path_unk)/str(instance.user)/'origin_unknown'/ \
            f'{filename}_correction-{now.strftime("%Y_%m_%d_%H_%M_%S")}.vtt'

class TranscriptionCorrection(models.Model):
    user = models.ForeignKey(auth.get_user_model(), on_delete=models.CASCADE, related_name='corrections')
    task = models.ForeignKey(TranscriptionTask, on_delete=models.CASCADE, related_name='corrections', blank=True, null=True)
    correction_file = models.FileField(upload_to=upload_correction)
    first_commit = models.DateTimeField(auto_now_add=True)
    last_commit = models.DateTimeField(verbose_name='last upload', auto_now=True)
    
    def __str__(self):
        return str(self.user) + 'correction done task_id: ' + str(self.task_id)

    @property
    def vtt(self):
        with self.correction_file.open('r') as file:
            return file.read()



def upload_audio(instance, fn):
    path = pathlib.PurePath('audio_clips')/instance.task.task_name/str(instance.user)
    ext = pathlib.PurePath(fn).suffix
    date_string = instance.created.strftime("%Y_%m_%d_%H_%M_%S")
    return path/f'{date_string}{ext}'

class CommandClip(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(auth.get_user_model(), on_delete=models.CASCADE, related_name='clips')
    task = models.ForeignKey(TranscriptionTask, on_delete=models.CASCADE, related_name='clips')

    audio = models.FileField(upload_to=upload_audio)

    original_text = models.TextField(blank=True)
    corrected_text = models.TextField(blank=True)
    context_before = models.TextField(blank=True)
    context_after = models.TextField(blank=True)

    context_start = models.TimeField()
    text_start = models.TimeField()
    text_end = models.TimeField()
    context_end = models.TimeField()



class TaskAssignment(models.Model):

    assignee = models.ForeignKey(auth.get_user_model(), on_delete=models.CASCADE, related_name='assignments_received')
    owner = models.ForeignKey(auth.get_user_model(), on_delete=models.CASCADE, related_name='assignments_made',
        limit_choices_to={'can_make_assignments': True})

    task = models.ForeignKey(TranscriptionTask, on_delete=models.CASCADE, related_name='assignments')

    created = models.DateTimeField(auto_now_add=True)

    #TODO maybe add unique constraint on assignee and task


