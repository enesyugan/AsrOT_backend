from . import models
from users.models import CustomUser

def get_user_list(*, filters=None):
    filters = filters or {}

    qs = CustomUser.objects.all()
    return qs.filter(**filters)

def correction_list(*, filters=None):
    filters = filters or {}

    qs = models.TranscriptionCorrection.objects.all()
    return qs.filter(**filters)

def task_list(*, filters=None):
    filters = filters or {}

    qs = models.TranscriptionTask.objects.all()
    return qs.filter(**filters)

def path_get(*, filters=None):
    filters = filters or {}

    qs = models.TranscriptionTask.objects.all()
    qs =  qs.filter(**filters)
    if len(qs) > 1:
        print("ERROR: multiple entries with task_id: {}".format(task_id))
        return None
    else:
        return qs.last()
