import json
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.decorators.http import require_GET
from django.views.generic import CreateView, UpdateView

from publications.models import Publication
from .forms import UpdateProfileForm, UpdateUserForm
from .models import CustomUser, Profile


class SignUpView(CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"


class ProfileView(LoginRequiredMixin, View):
    template_name = "accounts/profile.html"

    def get(self, request):
        user_form = UpdateUserForm(instance=request.user)
        profile_form = UpdateProfileForm(instance=request.user.profile)
        authored_publications = Publication.objects.filter(
            authors__user=request.user
        ).distinct().prefetch_related("authors__user")

        return render(request, self.template_name, {
            'user_form': user_form,
            'profile_form': profile_form,
            'publications': authored_publications
        })


class EditProfileView(LoginRequiredMixin, UpdateView):
    model = Profile
    form_class = UpdateProfileForm
    template_name = "accounts/edit_profile.html"

    def get_object(self, **kwargs):
        return self.request.user.profile

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'user_form' not in context:
            context['user_form'] = UpdateUserForm(instance=self.request.user)
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        user_form = UpdateUserForm(request.POST, instance=request.user)
        profile_form = self.get_form()

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile = profile_form.save(commit=False)

            raw_interests = self.request.POST.get('research_interests_input', '[]')
            profile.research_interests = self._handle_research_interests(raw_interests)

            profile.save()
            messages.success(request, "Profile updated successfully")
            return redirect("profile")

        return self.render_to_response(self.get_context_data(
            user_form=user_form,
            form=profile_form
        ))

    @staticmethod
    def _handle_research_interests(raw_input):
        keywords = []
        for entry in json.loads(raw_input):
            keyword = entry['value']
            keywords.append(keyword)

        return keywords


# @login_required
# def profile(request):
#     user = request.user
#     authored_publications = Publication.objects.filter(
#         authors__user=user
#     ).distinct().prefetch_related('authors__user')
#
#     if request.method == "POST":
#         user_form = UpdateUserForm(request.POST, instance=request.user)
#         profile_form = UpdateProfileForm(request.POST, request.FILES, instance=request.user.profile)
#
#         if user_form.is_valid() and profile_form.is_valid():
#             user_form.save()
#             profile_form.save()
#             messages.success(request, "Profile updated successfully.")
#             return redirect("profile")
#     else:
#         user_form = UpdateUserForm(instance=request.user)
#         profile_form = UpdateProfileForm(instance=request.user.profile)
#
#     return render(request, 'accounts/profile.html', {
#         'user_form': user_form,
#         'profile_form': profile_form,
#         'publications': authored_publications
#     })


@require_GET
def search_accounts(request):
    query = request.GET.get('q', '')
    users = CustomUser.objects.filter(first_name__icontains=query)[:10]
    return JsonResponse([
        {'value': f"{u.first_name} {u.last_name}", 'id': str(u.id)}
        for u in users
    ], safe=False)
