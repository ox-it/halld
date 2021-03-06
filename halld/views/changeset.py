import http.client

from django.http import HttpResponse

from .. import exceptions
from .. import renderers
from ..models import Changeset
from .base import HALLDView
from .mixins import JSONRequestMixin

class ChangesetView(JSONRequestMixin, HALLDView):
    def get_new_changeset(self, data):
        if not self.request.user.is_authenticated():
            raise exceptions.Forbidden(self.request.user)
        return Changeset(base_href=self.request.build_absolute_uri(),
                         author=self.request.user,
                         data=data)

class ChangesetListView(ChangesetView):
    def post(self, request):
        data = self.get_request_json('application/json')
        changeset = self.get_new_changeset(data)
        changeset.perform(multiple=True,
                          object_cache=request.object_cache)
        return HttpResponse(status=http.client.NO_CONTENT)

class RegenerateAllView(ChangesetView):
    def post(self, request):
        changeset = self.get_new_changeset({'description': 'Regenerate all (POST)',
                                            'regenerateAll': True})
        changeset.perform(multiple=True,
                          object_cache=request.object_cache)
        return HttpResponse(status=http.client.NO_CONTENT)
