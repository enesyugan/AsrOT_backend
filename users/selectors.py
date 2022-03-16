from .models import CustomUser

def get_user_list(*, filters=None):
    filters = filters or {}

    qs = CustomUser.objects.all()
    return qs.filter(**filters)

def get_user(email):
    return CustomUser.objects.get(email=email)