# myapp/views.py
from django.shortcuts import render

def home(request):
    return render(request, 'home.html')  # Or return HttpResponse('Hello World') for testing
