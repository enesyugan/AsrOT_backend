from django.db import models
from django.utils import timezone

from users import models as u_models

def get_default_my_date():
   return timezone.now()

class TranscriptionTask(models.Model):
    task_id = models.CharField(max_length=500, blank=False) ## mit uuid ein id generieren dann kann man darüber bspw status abfrage machen
    user = models.ForeignKey(u_models.CustomUser, on_delete=models.CASCADE)
    task_name = models.CharField(max_length=500, blank=False)
    file_size = models.IntegerField(blank=False)
    audio_filename = models.CharField(max_length=1000, blank=False)
    data_path = models.CharField(max_length=1000, blank=False)
    status = models.CharField(max_length=500, blank=False) #converting, segmenting,...
    date_time = models.DateTimeField(default=get_default_my_date)
    language = models.CharField(max_length=500, blank=False)
    transcription_hypo = models.CharField(max_length=1000, blank=True)
    text_hypo = models.CharField(max_length=1000, blank=True)
    encoding = models.CharField(max_length=500, blank=False)


    def __str__(self):
        return str(self.audio_filename) + ' language: ' + str(self.language)

class TranscriptionCorrection(models.Model):
    user = models.ForeignKey(u_models.CustomUser, on_delete=models.CASCADE)
    task_id = models.ForeignKey(TranscriptionTask, on_delete=models.CASCADE, blank=True, null=True)
    transcription_correction = models.CharField(max_length=1000, blank=False)    
    first_commit = models.DateTimeField(default=timezone.now)
    last_commit = models.DateTimeField(verbose_name='last upload', auto_now=True)
    
    def __str__(self):
        return str(self.user) + 'correction done task_id: ' + str(task_id)
