import jsonpointer

class Data(dict):
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
