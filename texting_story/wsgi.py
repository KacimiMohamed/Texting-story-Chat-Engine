"""
WSGI config for texting_story project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "texting_story.settings")

application = get_wsgi_application()
