import collections

import jsonpointer

class Data(dict):
    class IdentifierDict(collections.defaultdict):
        def __init__(self, stable):
            self._stable = stable
        def __missing__(self, key):
            return self._stable[key]
        def keys(self):
            return iter(set(super(Data.IdentifierDict, self).keys() | set(self._stable)))

    def __init__(self, *args, **kwargs):
        self['stableIdentifier'] = {}
        self['identifier'] = self.IdentifierDict(self['stableIdentifier'])
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
