"""
Custom DRF permission classes for the API.

This module defines permissions such as IsOwnerOrReadOnly, which allows unrestricted read access to objects,
but restricts write operations to the user who owns (added_by) the object.
applications.API.permissions


"""

from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an insult to edit/delete it.
    """

    def has_object_permission(self, request, view, obj) -> bool:
        # Read permissions are allowed to any request (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            return True
        return True if request.user.is_staff else obj.added_by == request.user
