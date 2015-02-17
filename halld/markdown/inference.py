import jsonpointer
import markdown

from .conf import MARKDOWN_PARAMS
from ..inference import FromPointers

class Markdown(FromPointers):
    def __call__(self, resource, data, **kwargs):
        for pointer in self.pointers:
            try:
                result = data.resolve(pointer)
                data.set(self.target, markdown.markdown(result, **MARKDOWN_PARAMS))
                return
            except jsonpointer.JsonPointerException:
                pass
