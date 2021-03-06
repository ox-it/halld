import abc
import enum

import jsonpatch

from .. import exceptions

class UpdateResult(enum.Enum):
    created = 1
    modified = 2
    deleted = 3
    moved = 4

class Update(object, metaclass=abc.ABCMeta):
    """
    Abstract base class for objects to mutate Source objects.
    """

    # So that some updates (e.g. PUT) can not require that the source
    # already exists
    require_source_exists = True
    will_delete = False

    @abc.abstractclassmethod
    def from_json(cls, committer, data):  # @NoSelf
        pass

    @abc.abstractmethod
    def __call__(self, author, committer, source):
        pass

class PutUpdate(Update):
    require_source_exists = False

    def __init__(self, data):
        self.data = data

    @property
    def will_delete(self):
        return self.data is None

    @classmethod
    def from_json(cls, data):
        #if data['data'] is None:
        #    return DeleteUpdate.from_json(data)
        return cls(data['data'])

    def __call__(self, author, committer, source):
        if self.data == source.data:
            return
        if self.data is None:
            delete_update = DeleteUpdate()
            return delete_update(author, committer, source)
        else:
            creating = not source.pk
            was_deleted = source.deleted
            source.deleted = False
            source.data = self.data
            if was_deleted or creating:
                return UpdateResult.created
            else:
                return UpdateResult.modified

class PatchUpdate(Update):
    require_source_exists = False

    def __init__(self, patch, create_empty_if_missing=False):
        self.patch = patch
        self.create_empty_if_missing = create_empty_if_missing

    @classmethod
    def from_json(cls, data):
        return cls(data['patch'], data.get('createEmptyIfMissing', False))

    def __call__(self, author, committer, source):
        if not committer.has_perm('halld.change_source', source):
            raise exceptions.Forbidden(committer)
        if not self.patch:
            return
        if not self.create_empty_if_missing and not source.pk:
            raise exceptions.NoSuchSource(source.href)
        if source.deleted:
            raise exceptions.CantPatchDeletedSource

        data = jsonpatch.apply_patch(source.data, self.patch)
        source.validate_data(data)
        source.data = data

        return UpdateResult.modified

class DeleteUpdate(Update):
    @classmethod
    def from_json(cls, data):
        return cls()

    will_delete = True

    def __call__(self, author, committer, source):
        if not committer.has_perm('halld.delete_source', source):
            raise exceptions.Forbidden(committer)
        if not source.deleted:
            source.data = None
            return UpdateResult.deleted

class MoveUpdate(Update):
    def __init__(self, target_resource_href):
        self.target_resource_href = target_resource_href

    @classmethod
    def from_json(cls, data):
        return cls(data['targetResourceHref'])

    def __call__(self, author, committer, source):
        if not committer.has_perm('halld.change_source', source):
            raise exceptions.Forbidden(committer)
        if source.resource_id == self.target_resource_href:
            return
        source.resource_id = self.target_resource_href
        return UpdateResult.moved
