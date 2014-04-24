from django.contrib import admin

from . import models

class ResourceAdmin(admin.ModelAdmin):
    list_display = ['type', 'identifier', 'uri', 'version', 'modified']
    list_filter = ['type']

class IdentifierAdmin(admin.ModelAdmin):
    list_display = ['resource', 'scheme', 'value']
    list_filter = ['scheme']

class LinkAdmin(admin.ModelAdmin):
    list_display = ['active', 'type', 'passive']
    list_filter = ['type']

class SourceAdmin(admin.ModelAdmin):
    list_display = ['resource', 'type', 'author', 'committer', 'version', 'deleted']

admin.site.register(models.ResourceType)
admin.site.register(models.Resource, ResourceAdmin)
admin.site.register(models.LinkType)
admin.site.register(models.Link, LinkAdmin)
admin.site.register(models.SourceType)
admin.site.register(models.Source, SourceAdmin)
admin.site.register(models.Identifier, IdentifierAdmin)