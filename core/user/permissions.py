from rest_framework import permissions

class IsAdminOrOwner(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.role == "admin":
            return True
        if request.user.role == "vendor" and obj.seller == request.user:
            return request.method in ["GET", "POST", "PUT", "PATCH", "DELETE"]
        if request.user.role == "customer":
            return request.method == "GET"
        return False
