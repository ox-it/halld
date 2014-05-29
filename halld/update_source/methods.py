import abc
import enum

from django.core.exceptions import PermissionDenied
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

    @abc.abstractclassmethod
    def from_json(cls, committer, data):  # @NoSelf
        pass

    @abc.abstractmethod
    def __call__(self, source):
        pass

class PutUpdate(Update):
    def __init__(self, data):
        self.data = data

    @classmethod
    def from_json(cls, data):
        #if data['data'] is None:
        #    return DeleteUpdate.from_json(data)
        return cls(data['data'])

    def __call__(self, author, committer, source):
        was_deleted = source.deleted
        source.deleted = False
        data = source.filter_data(author, source.data)
        patch = jsonpatch.make_patch(data, self.data)
        update = PatchUpdate(patch)
        try:
            result = update(author, committer)
        except Exception:
            source.deleted = was_deleted
            raise
        if was_deleted:
            return UpdateResult.created
        else:
            return result

class PatchUpdate(Update):
    def __init__(self, patch):
        self.patch = patch

    @classmethod
    def from_json(cls, data):
        return cls(data['patch'])

    def __call__(self, author, committer, source):
        if not committer.has_perm('halld.change_source', source):
            raise PermissionDenied
        if not self.patch:
            return
        if source.deleted:
            raise exceptions.CantPatchDeletedSource

        if not source.patch_acceptable(committer, self.patch):
            raise exceptions.PatchUnacceptable

        # The effect of applying the patch should be the same regardless of
        # whether it's applied before or after filtering. This ensures the
        # committer isn't trying to change something that would ordinarily
        # be filtered.
        filtered_patched = source.filter_data(self.committer, jsonpatch.apply_patch(source.data, self.patch))
        patched_filtered = jsonpatch.apply_patch(source.filter_data(self.committer, source.data), self.patch)
        if filtered_patched != patched_filtered:
            raise exceptions.PatchUnacceptable

        data = jsonpatch.apply_patch(source.data, self.patch)
        source.validate_data(data)
        source.data = data

        return UpdateResult.modified

class DeleteUpdate(Update):
    @classmethod
    def from_json(cls, data):
        return cls()

    def __call__(self, author, committer, source):
        if not self.has_perm('halld.delete_source', source):
            raise PermissionDenied
        if not source.deleted:
            source.deleted = True
            source.data = None
            return UpdateResult.deleted

class MoveUpdate(Update):
    def __init__(self, author, committer, target_resource_href):
        super(MoveUpdate, self).__init__(committer)
        self.target_resource_href = target_resource_href

    @classmethod
    def from_json(cls, committer, data):
        return cls(committer, data['targetResourceHref'])

    def __call__(self, committer, source):
        raise NotImplementedError