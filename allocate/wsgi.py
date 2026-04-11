"""
WSGI config for allocate project.
"""

import newrelic.agent
newrelic.agent.initialize('C:/Users/bhati/New folder (5)/New/allocate/newrelic.ini')

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allocate.settings')

application = get_wsgi_application()
application = newrelic.agent.wsgi_application()(application)