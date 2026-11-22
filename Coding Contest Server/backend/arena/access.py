from django.contrib.auth import logout
from .models import Profile

class RosterAccess:
    def __init__(self,get_response):
        self.get_response=get_response

    def __call__(self,request):
        user=request.user
        if user.is_authenticated:
            allowed=(user.username=="organizer" if user.is_staff or user.is_superuser else
                     Profile.objects.filter(user=user).exclude(ecode_batch="").exists())
            if not allowed:
                logout(request)
        return self.get_response(request)
