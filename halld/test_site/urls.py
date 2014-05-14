from django.conf.urls import patterns, url, include
from django.contrib import admin

admin.autodiscover()

urlpatterns = patterns('',
    url(r'^', include('halld.files.urls', 'halld-files')),
    url(r'^', include('halld.urls', 'halld')),
)
