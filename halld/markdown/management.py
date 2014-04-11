# Installs the markdown format checker for JSONSchema

from jsonschema._format import _checks_drafts, str_types
import markdown

from .conf import MARKDOWN_PARAMS

@_checks_drafts("markdown")
def is_markdown(instance):
    if not isinstance(instance, str_types):
        return True
    try:
        markdown.markdown(instance, **MARKDOWN_PARAMS)
