from django.contrib.auth.hashers import make_password
from rest_framework import serializers

from . import models
from . import selectors

def user_register(email, password, langs):
    user = models.CustomUser(
        email=email,
        password=make_password(password=password),
    )

    try:
        user.full_clean()
    except Exception as e:
        raise serializers.ValidationError(e)

    user.save()

    user.languages.set(langs)
