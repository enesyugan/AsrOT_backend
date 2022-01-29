from . import models

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
