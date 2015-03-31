from django.db.models.signals import post_syncdb
from django.contrib.auth import get_user_model

from .. import get_halld_files_config
from .. import models

def ensure_file_metadata_user(sender, **kwargs):
    """
    Makes sure there's a superuser for updating file metadata sources
    """
    User = get_user_model()
    user, _ = User.objects.get_or_create(username=get_halld_files_config().file_metadata_user)
    user.is_superuser = True
    user.save()

post_syncdb.connect(ensure_file_metadata_user, sender=models)
