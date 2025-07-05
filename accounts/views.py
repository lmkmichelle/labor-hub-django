from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader

def login(request):
    template = loader.get_template('../templates/accounts/login.html')
    return HttpResponse(template.render())
