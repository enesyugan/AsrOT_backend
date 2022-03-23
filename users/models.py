from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .managers import CustomUserManager


class Language(models.Model):
    short = models.SlugField(max_length=5, primary_key=True, verbose_name='ISO 639 code')
    english_name = models.CharField(max_length=50)
    native_name = models.CharField(max_length=50, blank=True)

    has_asr = models.BooleanField(default=False, verbose_name='Has ASR',
        help_text='Set this to true if the ASR system supports this language')
    custom_asr_id = models.CharField(blank=True, max_length=50, verbose_name='Custom ASR iD',
        help_text='Set this to the identifier that your ASR system uses for the language, defaults to the value of short')

    @property
    def asr_id(self):
        if self.custom_asr_id:
            return self.custom_asr_id
        else:
            return self.short

    def __str__(self):
        return f'{self.short}: {self.english_name} ({self.native_name})'


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(_('email address'), unique=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(verbose_name='last login', auto_now=True)
    restricted_account = models.BooleanField(default=True)
    can_make_assignments = models.BooleanField(default=False)
    
    languages = models.ManyToManyField(Language, related_name='speakers')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        verbose_name = 'User'

    def __str__(self):
        return self.email
