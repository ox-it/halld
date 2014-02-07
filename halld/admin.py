from django.contrib import admin

from . import models

class ResourceAdmin(admin.ModelAdmin):
    list_display = ['type', 'identifier', 'uri', 'version', 'modified']
    list_filter = ['type']

class IdentifierAdmin(admin.ModelAdmin):
    list_display = ['resource', 'scheme', 'value']
    list_filter = ['scheme']

class LinkAdmin(admin.ModelAdmin):
    list_display = ['active', 'link_name', 'passive', 'inverted']
    list_filter = ['link_name']

admin.site.register(models.Resource, ResourceAdmin)
admin.site.register(models.Link, LinkAdmin)
admin.site.register(models.Source)
admin.site.register(models.SourceData)
admin.site.register(models.Identifier, IdentifierAdmin)