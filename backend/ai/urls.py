from django.urls import path

from voice.views import voice_command

urlpatterns = [
    path("voice/command/", voice_command),
]
