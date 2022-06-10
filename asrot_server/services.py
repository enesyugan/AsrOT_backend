import email
from rest_framework import serializers as rf_serializers
from django.core.files import base, uploadedfile
from django.contrib import auth

from . import models, utils, selectors
from AsrOT import settings

from datetime import datetime
import pathlib, threading

print(settings.MEDIA_ROOT)

def selfassign_task(task_id):
    task = selectors.path_get(filters={'task_id':task_id})
    task.assigned = True
    try:
        task.full_clean()
        task.save()
    except Exception as e:
        print(e)
        raise rf_serializers.ValidationError(e)

    task.save()

    user.assigned_task=task_id
    try:
        user.full_clean()
        user.save()
    except Exception as e:
        print(e)
        raise rf_serializers.ValidationError(e)

    user.save()
    return True

def create_task(task_name, user, audiofile, language):
    ext = pathlib.PurePath(audiofile.name).suffix
    file_name = pathlib.PurePath(audiofile.name).stem
    file_name = file_name.replace('/','_').replace('\\','_').replace(' ','-')
    now = datetime.now()
    date_string = now.strftime("%Y_%m_%d_%H_%M_%S")
    file_name = f"{file_name}-{date_string}"
    file_sizemb = (audiofile.size // 1000000)
    print("File size: {} mb".format(file_sizemb))
    print(user)
    print(user.restricted_account)
    if user.restricted_account:
        if file_sizemb > 800:
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
        new_task.save()
    except Exception as e:
        print("Error: {}".format(e))
        raise rf_serializers.ValidationError(e)
    print("dd")   
    new_task.save()
    print("RRR")
    if isinstance(audiofile, uploadedfile.InMemoryUploadedFile):
        audio = (audiofile.file).getvalue()
    if isinstance(audiofile, uploadedfile.TemporaryUploadedFile):
        audiofile.seek(0)
        audio = audiofile.read()

    #daemon=False makes sure that the program doesn't finish if a pipe is still running
    thread = threading.Thread(target=utils.pipe, args=(new_task, audio, ext, ), daemon=False)
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


def create_vtt_correction(user, vtt_data, task_id, vtt_name, finished=False):
    if task_id is None:
        for line in vtt_data.split('\n'):
                if "NOTE task_id:" in line: 
                    task_id = line.strip().split()[-1]
                    print("TASK ID: {}".format(task_id))
                    break
    
    try:
        task = models.TranscriptionTask.objects.get(task_id=task_id)
    except models.TranscriptionTask.DoesNotExist as e:
        task = None

    if user.id is None:
        unk_email = 'unknown@unknown.com'
        user_model = auth.get_user_model()
        try:
            user = user_model._default_manager.get(email=unk_email)
        except user_model.DoesNotExist as e:
            user = user_model._default_manager.create_user(unk_email, password='')
            user.set_unusable_password()
            user.save()

    vtt_file = base.ContentFile(vtt_data, vtt_name)
 
    if finished:
        try:
            correction = models.TranscriptionCorrection.objects.filter(task=task,finished=finished).latest('last_commit')
            print(correction.correction_file)    
            #what if task is None
            correction.correction_file=vtt_file      
        except Exception as e:
            print(f"No correction found: {e}")
            correction = models.TranscriptionCorrection(
                user=user,
                correction_file=vtt_file,
                task=task,
                finished=finished
            )
    else:
  #  vtt_file = base.ContentFile(vtt_data, vtt_name)
        correction = models.TranscriptionCorrection(
            user=user,
            correction_file=vtt_file,
            task=task,
            finished=finished
        )
    try:
        correction.full_clean()
        correction.save()
    except Exception as e:
        print(f"Error: {e}")
        #raise rf_serializers.ValidationError(e) das fürt im Frontend zu error
    
    print(correction)
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
