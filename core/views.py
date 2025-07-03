from django.http import HttpResponse
from django.template import loader

from django.shortcuts import render

# Create your views here.
def home(request):
    template = loader.get_template('../templates/core/home.html')
    return HttpResponse(template.render())
