from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView

from accounts.forms import UpdateProfileForm
from publications.models import Publication

class SignUpView(CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"

@login_required
def profile(request):
    if (request.method == "POST"):
        user_form = UpdateProfileForm(request.POST, instance=request.user)
        profile_form = UpdateProfileForm(request.POST, request.FILES, instance=request.user.profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Profile updated successfully")
            return redirect(to="profile")
    else:
        user = request.user
        authored_publications = Publication.objects.filter(
            authors__user=user
        ).distinct().prefetch_related('authors__user')

        return render(request, 'accounts/profile.html', {
            'user': user,
            'publications': authored_publications
        })
