import collections

import jsonpointer

class Data(object):
    class StableIdentifierDict(dict):
        def __init__(self, other={}):
            self._other = other
        def __setitem__(self, key, value):
            self._other[key] = value
            super().__setitem__(key, value)
        def update(self, *args, **kwargs):
            self._other.update(*args, **kwargs)
            super().update(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        self._data = dict(*args, **kwargs)
        self['identifier'] = {}
        self['stableIdentifier'] = Data.StableIdentifierDict(self['identifier'])

    def __getitem__(self, key):
        return self._data[key]
    def __setitem__(self, key, value):
        self._data[key] = value
    def __delitem__(self, key):
        del self._data[key]
    def __contains__(self, key):
        return key in self._data
    def __len__(self):
        return len(self._data)
    def __iter__(self):
        return iter(self._data)
    def get(self, key, default=None):
        return self._data.get(key, default)
    def pop(self, *args, **kwargs):
        return self._data.pop(*args, **kwargs)

    def __eq__(self, other):
        if isinstance(other, Data):
            other = other._data
        return self._data == other

    def set(self, ptr, value):
        if not isinstance(ptr, jsonpointer.JsonPointer):
            ptr = jsonpointer.JsonPointer(ptr)
        try:
            ptr.set(self._data, value)
        except jsonpointer.JsonPointerException:
            for i in range(1, len(ptr.parts)):
                subptr = jsonpointer.JsonPointer.from_parts(ptr.parts[:i])
                if not subptr.get(self._data, None):
                    subptr.set(self._data, {})
            ptr.set(self._data, value)

    def resolve(self, ptr, default=jsonpointer._nothing):
        if not isinstance(ptr, jsonpointer.JsonPointer):
            ptr = jsonpointer.JsonPointer(ptr)
        return ptr.get(self._data, default)

    def copypointer(self, src, dst):
        self.set(dst, self.resolve(src))
