"""
WSGI config for AsrOT project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/wsgi/
"""
##### work around to change to conda env django from empty vRel
python_home = '/home/relater/anaconda3/envs/AsrOT'

import sys
import site
import logging

# Calculate path to site-packages directory.
python_version = '.'.join(map(str, sys.version_info[:2]))
site_packages = python_home + '/lib/python%s/site-packages' % python_version
#site_packages = '/home/relater/anaconda3/envs/django/lib/python3.8/site-packages'
logger = logging.getLogger(__name__)
logger.info(site_packages)
# Add the site-packages directory.
site.addsitedir(site_packages)
#####

import os

import getpass
import sys
print(getpass.getuser(),file=sys.stderr)
print(sys.executable,file=sys.stderr)
print(sys.path,file=sys.stderr)

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AsrOT.settings')

application = get_wsgi_application()
