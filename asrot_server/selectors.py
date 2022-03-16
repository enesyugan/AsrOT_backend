from . import models

#This is meant to be passed on to modules importing asrot_server.selectors DO NOT REMOVE
from users.selectors import get_user_list, get_user

def get_assigned_tasks(user, owner=None):
    if owner is None:
        return user.assigned_tasks.all().distinct()
    else:
        return user.assigned_tasks.filter(assignments__owner=owner).distinct()

def get_assigned_users(task, owner=None):
    if owner is None:
        return task.assignees.all().distinct()
    else:
        return task.assignees.filter(assignments_received__owner=owner).distinct()

def get_managed_assignments(owner, task=None, assignee=None):
    filters = {}
    if task is not None:
        filters['task'] = task
    if assignee is not None:
        filters['assignee'] = assignee
    return owner.assignments_made.filter(**filters)


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
