from . import models

def get_user_list(*, filters=None):
    filters = filters or {}

    qs = models.CustomUser.objects.all()
    return qs.filter(**filters)

def get_user(email):
    return models.CustomUser.objects.get(email=email)


def get_language_list(*, asr=None, filters=None):
    filters = filters or {}
    if asr:
        filters['has_asr'] = True
    
    return models.Language.objects.filter(**filters)

def get_language(short):
    return models.Language.objects.get(short=short)