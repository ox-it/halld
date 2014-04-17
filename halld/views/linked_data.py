from django.core.urlresolvers import reverse
from django.views.generic import View
from django_conneg.http import HttpResponseSeeOther

__all__ = ['IdView']

class IdView(View):
    def dispatch(self, request, resource_type, identifier):
        return HttpResponseSeeOther(reverse('resource', args=[resource_type, identifier]))

