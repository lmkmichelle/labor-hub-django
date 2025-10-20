
from django.views.generic import ListView
from django.shortcuts import render

from seminars.models import Seminar


class SeminarsListView(ListView):
    model = Seminar
    template_name = 'seminars/seminars_list.html'
    context_object_name = 'seminars'
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        return context
