import datetime
from django.db import models
from django.contrib import auth
from django.core.files.storage import default_storage

from functools import partial as part
import uuid, pathlib

from AsrOT import settings


print(settings.BASE_DIR)

def base_path(instance):
    return pathlib.PurePath(settings.MEDIA_ROOT)/instance.language.upper()/instance.audio_filename



def upload_media(instance, fn):
    filename = pathlib.PurePath(fn)
    return base_path(instance)/f'{instance.audio_filename}__upload{filename.suffix}'

def upload_data(instance, fn, filetype):
    return base_path(instance)/f'{instance.audio_filename}.{filetype}'

def upload_logs(instance, fn, filetype):
    return base_path(instance)/'log'/f'{filetype}.log'

class TranscriptionTask(models.Model):
    task_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False) ## mit uuid ein id generieren dann kann man darüber bspw status abfrage machen
    user = models.ForeignKey(auth.get_user_model(), on_delete=models.CASCADE, related_name='owned_tasks')
    task_name = models.CharField(max_length=500)
    audio_filename = models.CharField(max_length=1000, null=False)
    audio_filesize = models.IntegerField(null=False)
    media_hash = models.CharField(max_length=256,default="")

    assignees = models.ManyToManyField(auth.get_user_model(), 
        through='TaskAssignment', through_fields=('task', 'assignee'), 
        related_name='assigned_tasks')

    status = models.CharField(max_length=500, blank=True) #converting, segmenting,...
    date_time = models.DateTimeField(auto_now_add=True)
    language = models.CharField(max_length=500, null=False)

    assigned = models.BooleanField(default=False)
    corrected = models.BooleanField(default=False)

    #`blank=True` `null=True` since the files are created and saved later in the pipeline
    media_file = models.FileField(upload_to=upload_media, max_length=300)
    wav_file = models.FileField(upload_to=part(upload_data, filetype='wav'), blank=True, null=True, max_length=300)
    seg_file = models.FileField(upload_to=part(upload_data, filetype='seg'), blank=True, null=True, max_length=300)
    stm_file = models.FileField(upload_to=part(upload_data, filetype='stm'), blank=True, null=True, max_length=300)
    txt_file = models.FileField(upload_to=part(upload_data, filetype='txt'), blank=True, null=True, max_length=300)
    vtt_file = models.FileField(upload_to=part(upload_data, filetype='vtt'), blank=True, null=True, max_length=300)

    conversion_log = models.FileField(upload_to=part(upload_logs, filetype='conversion'), blank=True, null=True, max_length=300)
    seg_log = models.FileField(upload_to=part(upload_logs, filetype='segmentation'), blank=True, null=True, max_length=300)
    asr_log = models.FileField(upload_to=part(upload_logs, filetype='asr'), blank=True, null=True, max_length=300)
    vtt_log = models.FileField(upload_to=part(upload_logs, filetype='vtt'), blank=True, null=True, max_length=300)

    class Meta:
        ordering = ['-date_time']

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
        try:
            with self.vtt_file.open('r') as file:
                return file.read()
        except Exception as e:
            print(f"Error: {e}")



def upload_correction(instance, fn):
    filename = pathlib.PurePath(fn)
  
    if instance.task != None:
        # Changing the name can't be done in a Storage class, since it should only be used for task-related files
        i = 0
        base_name = base_path(instance.task)/"correct-vtt"
        base_name = base_name/f'{instance.task.audio_filename}__{instance.user.pk:04d}__correct'
 #       print(base_name)
        if instance.finished:
            base_name = f'{base_name}__finished'

        while True:
          #  file_name = base_name/f'{instance.task.audio_filename}__{instance.user.pk:04d}__correct__{i:03d}.vtt'
            file_name = f'{base_name}__{i:03d}.vtt'
            if not default_storage.exists(file_name):
                break
            i += 1
        return file_name  

    else:
        now = datetime.datetime.now()
        return pathlib.PurePath(settings.MEDIA_ROOT)/str(instance.user)/'origin_unknown'/ \
            f'{filename}_correction-{now.strftime("%Y_%m_%d_%H_%M_%S")}.vtt'

class TranscriptionCorrection(models.Model):
    user = models.ForeignKey(auth.get_user_model(), on_delete=models.CASCADE, related_name='corrections')
    task = models.ForeignKey(TranscriptionTask, on_delete=models.CASCADE, related_name='corrections', blank=True, null=True)
    correction_file = models.FileField(upload_to=upload_correction, max_length=300)
    first_commit = models.DateTimeField(auto_now_add=True)
    last_commit = models.DateTimeField(verbose_name='last upload', auto_now=True)
    finished = models.BooleanField(default=False)

    class Meta:
        ordering = ['task', 'user', '-last_commit']
    
    def __str__(self):
        return str(self.user) + ' correction table task_id: ' + str(self.task_id)

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

    class Meta:
        ordering = ['task', 'user', '-created']



class TaskAssignment(models.Model):

    assignee = models.ForeignKey(auth.get_user_model(), on_delete=models.CASCADE, related_name='assignments_received')
    owner = models.ForeignKey(auth.get_user_model(), on_delete=models.CASCADE, related_name='assignments_made',
        limit_choices_to={'can_make_assignments': True})

    task = models.ForeignKey(TranscriptionTask, on_delete=models.CASCADE, related_name='assignments')

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']

    #TODO maybe add unique constraint on assignee and task


