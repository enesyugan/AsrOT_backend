from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import CustomUser, Language


class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    verbose_name = 'User'
    list_display = ('email', 'is_staff', 'is_active','restricted_account', 'can_make_assignments', )
    list_filter = ('is_staff', 'is_active','restricted_account', 'can_make_assignments', )
    fieldsets = (
        (None, {'fields': ('email', 'password', 'languages', )}),
        ('Permissions', {'fields': ('is_staff', 'is_active', 'restricted_account', 'can_make_assignments', )}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'is_staff', 'is_active', 'restricted_account', 'can_make_assignments', )}
        ),
    )
    search_fields = ('email',)
    ordering = ('email',)
    filter_horizontal = ('languages', )


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Language)
