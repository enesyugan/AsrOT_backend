from rest_framework import permissions


class CanMakeAssignments(permissions.BasePermission):

    message = 'Making and managing assignments not allowed'

    def has_permission(self, request, view):
        return request.user.can_make_assignments