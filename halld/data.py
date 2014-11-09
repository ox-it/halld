import collections

import jsonpointer

class Data(dict):
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
        self['identifier'] = {}
        self['stableIdentifier'] = Data.StableIdentifierDict(self['identifier'])
        super(Data, self).__init__(*args, **kwargs)

    def set(self, ptr, value):
        if not isinstance(ptr, jsonpointer.JsonPointer):
            ptr = jsonpointer.JsonPointer(ptr)
        try:
            ptr.set(self, value)
        except jsonpointer.JsonPointerException:
            for i in range(1, len(ptr.parts)):
                subptr = jsonpointer.JsonPointer.from_parts(ptr.parts[:i])
                if not subptr.get(self, None):
                    subptr.set(self, {})
            ptr.set(self, value)

    def resolve(self, ptr, default=jsonpointer._nothing):
        if not isinstance(ptr, jsonpointer.JsonPointer):
            ptr = jsonpointer.JsonPointer(ptr)
        return ptr.get(self, default)

    def copypointer(self, src, dst):
        self.setpointer(dst, self.getpointer(src))
