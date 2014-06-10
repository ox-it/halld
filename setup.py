from distutils.core import setup

# Idea borrowed from http://cburgmer.posterous.com/pip-requirementstxt-and-setuppy
install_requires, dependency_links = [], []
for line in open('requirements.txt'):
    line = line.strip()
    if line.startswith('-e'):
        dependency_links.append(line[2:].strip())
    elif line:
        install_requires.append(line)

try:
    import enum
except ImportError:
    install_requires.append('enum34')

setup(
    name='halld',
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
    install_requires=install_requires,
    dependency_links=dependency_links,
)

