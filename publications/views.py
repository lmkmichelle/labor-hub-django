from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader

def publications(request):
    template = loader.get_template('../templates/publications/publications.html')
    return HttpResponse(template.render())
