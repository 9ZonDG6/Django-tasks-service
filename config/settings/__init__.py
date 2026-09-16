from split_settings.tools import include

include("env.py", "django.py", "apps.py", "database.py", "jwt.py", "rest_framework.py", scope=globals())
