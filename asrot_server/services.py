from rest_framework import serializers as rf_serializers
from django.core.files import uploadedfile

from . import models, utils, selectors

from datetime import datetime
import pathlib, threading


def create_task(task_name, user, audiofile, language):
    ext = pathlib.PurePath(audiofile.name).suffix
    file_name = pathlib.PurePath(audiofile.name).stem
    file_name = file_name.replace('/','_').replace('\\','_')
    now = datetime.now()
    date_string = now.strftime("%Y_%m_%d_%H_%M_%S")
    file_name = f"{file_name}-{date_string}"
    file_sizemb = (audiofile.size // 1000000)
    print("File size: {} mb".format(file_sizemb))
    print(user)
    print(user.restricted_account)
    if user.restricted_account:
        if file_sizemb > 10:
            raise rf_serializers.ValidationError({"file size": "You have a restricted account. Your media file must be smaller than 10 mb. Please write an email to administrators to allow for unlimited upload size."})
    
    new_task = models.TranscriptionTask(
        task_name=task_name,
        user=user,
        audio_filename=file_name,
        audio_filesize=file_sizemb,
        language=language,
        media_file=audiofile,
    )
    try:
        new_task.full_clean()
    except Exception as e:
        raise rf_serializers.ValidationError(e)
    new_task.save()

    if isinstance(audiofile, uploadedfile.InMemoryUploadedFile):
        audio = (audiofile.file).getvalue()
    if isinstance(audiofile, uploadedfile.TemporaryUploadedFile):
        audiofile.seek(0)
        audio = audiofile.read()

    thread = threading.Thread(target=utils.pipe, args=(new_task, audio, ext, ))
    thread.start()

    return new_task


def create_correction_clip(task_id, user, audio, 
  original_text, corrected_text, context_before, context_after, 
  context_start, text_start, text_end, context_end, ):

    task = models.TranscriptionTask.objects.get(task_id=task_id)

    new_clip = models.CommandClip(
        user=user,
        task=task,
        audio=audio,
        original_text=original_text,
        corrected_text=corrected_text,
        context_before=context_before,
        context_after=context_after,
        context_start=context_start,
        text_start=text_start,
        text_end=text_end,
        context_end=context_end,
    )

    try:
        new_clip.full_clean()
    except Exception as e:
        raise rf_serializers.ValidationError(e)
    new_clip.save()

    return new_clip






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





