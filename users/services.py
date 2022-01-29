from rest_framework import serializers

from . import models
from . import selectors

def user_register(*, serializer: serializers.Serializer):
    user = models.CustomUser(**serializer.validated_data)

    try:
        user.full_clean()
    except Exception as e:
        raise serializers.ValidationError(e)

    user.save()
