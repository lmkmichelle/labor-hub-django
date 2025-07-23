import json
from io import BytesIO
from PIL import Image
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, Http404
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.decorators.http import require_GET
from django.views.generic import CreateView, UpdateView, ListView

from core.constants import COUNTRY_CHOICES
from publications.models import Publication
from .forms import UpdateProfileForm, UpdateUserForm, CustomLoginForm, UserApplicationForm
from .models import CustomUser, Profile, UserApplication


class ApplyView(CreateView):
    model = UserApplication
    form_class = UserApplicationForm
    success_url = reverse_lazy('application_submitted')
    template_name = 'accounts/apply.html'

    def form_valid(self, form):
        messages.success(
            self.request,
            "Your application has been submitted successfully! "
            "You will receive an email notification once it has been reviewed."
        )

        return super().form_valid(form)


class ApplicationSubmittedView(View):
    template_name = "accounts/application_submitted.html"

    def get(self, request):
        return render(request, self.template_name)

class CustomLoginView(LoginView):
    model = CustomUser
    form_class = CustomLoginForm
    success_url = reverse_lazy("/")
    template_name = "registration/login.html"


class ProfileView(View):
    template_name = "accounts/profile.html"

    def get(self, request, pk=None):
        if pk:
            try:
                profile_user = CustomUser.objects.get(pk=pk)
            except CustomUser.DoesNotExist:
                raise Http404("User not found")
        else:
            if not request.user.is_authenticated:
                return redirect("/login/")
            profile_user = request.user

        authored_publications = Publication.objects.filter(
            authors__user=profile_user
        ).distinct().prefetch_related("authors__user")

        return render(request, self.template_name, {
            'profile_user': profile_user,
            'user_profile': profile_user.profile,
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

            if 'avatar' in request.FILES:
                profile.avatar = self._crop(request.FILES['avatar'])
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

    def _crop(self, image_file, output_size=(218, 300)):
        with Image.open(image_file) as img:
            img = img.convert("RGB")

            target_ratio = output_size[0] / output_size[1]
            img_ratio = img.width / img.height

            if img_ratio > target_ratio:
                new_height = output_size[1]
                new_width = int(new_height * img_ratio)
            else:
                new_width = output_size[0]
                new_height = int(new_width / img_ratio)

            img = img.resize((new_width, new_height), Image.LANCZOS)

            left = (new_width - output_size[0]) // 2
            top = (new_height - output_size[1]) // 2
            right = left + output_size[0]
            bottom = top + output_size[1]
            img = img.crop((left, top, right, bottom))

            buffer = BytesIO()
            img.save(buffer, format="JPEG")
            buffer.seek(0)

            return InMemoryUploadedFile(
                buffer,
                field_name='avatar',
                name='avatar.jpg',
                content_type='image/jpeg',
                size=buffer.tell(),
                charset=None
            )
