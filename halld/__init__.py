from pkg_resources import get_distribution, DistributionNotFound
import os.path

from django.apps import apps as django_apps

default_app_config = 'halld.apps.HALLDConfig'

def get_halld_config():
    return django_apps.get_app_config('halld')


__distribution__ = 'halld'

# Kudos to http://stackoverflow.com/a/17638236

try:
    _dist = get_distribution(__distribution__)
    # Normalize case for Windows systems
    dist_loc = os.path.normcase(_dist.location)
    here = os.path.normcase(__file__)
    if not here.startswith(os.path.join(dist_loc, __distribution__)):
        # not installed, but there is another version that *is*
        raise DistributionNotFound
except DistributionNotFound:
    __version__ = 'dev'
else:
    __version__ = _dist.version

