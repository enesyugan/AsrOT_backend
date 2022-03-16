import email
from rest_framework import serializers as rf_serializers
from django.core.files import base, uploadedfile
from django.contrib import auth

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


def create_vtt_correction(user, vtt_data, task_id, vtt_name):

    if task_id is None:
        for line in vtt_data.split('\n'):
                if "NOTE task_id:" in line: 
                    task_id = line.strip().split()[-1]
                    print("TASK ID: {}".format(task_id))
                    break
    
    if task_id is None:
        task = None
    else:
        task = models.TranscriptionTask.objects.get(task_id=task_id)

    if user.id is None:
        #TODO this should be detached by accessing USERNAME_FIELD
        user, _ = auth.get_user_model().objects.get_or_create(email='unknown@unknown.com')

    vtt_file = base.ContentFile(vtt_data, vtt_name)

    correction = models.TranscriptionCorrection(
        user=user,
        correction_file=vtt_file,
        task=task,
    )

    try:
        correction.full_clean()
    except Exception as e:
        raise rf_serializers.ValidationError(e)
    correction.save()

    return correction


def create_single_assignment(owner, assignee_email, task_id):
    if not owner.can_make_assignments:
        raise rf_serializers.ValidationError('You are not allowed to make assignments')

    task = models.TranscriptionTask.objects.get(task_id=task_id)
    assignee = selectors.get_user(email=assignee_email)

    assignment = models.TaskAssignment(
        assignee=assignee,
        owner=owner,
        task=task,
    )

    try:
        assignment.full_clean()
    except Exception as e:
        raise rf_serializers.ValidationError(e)
    assignment.save()

    return assignment
