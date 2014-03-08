from distutils.core import setup

setup(
    name='oxpoints',
    version='0.1',
    packages=[
        'halld',
        'halld.management',
        'halld.pubsub',
        'halld.registry',
        'halld.test',
        'halld.test_site',
        'halld.util',
    ],
)

