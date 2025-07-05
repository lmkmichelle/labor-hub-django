from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def profile(request):
    user = request.user
    return render(request, 'accounts/profile.html', {'user': user})
