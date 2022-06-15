# Use the local settings from the gitmanager web app
# with some modifications for the Huey worker (task queue consumer).
# Dockerfile.huey adds gitmanager-cont-settings.py to the start of this file.

# Connect to the database in the gitmanager web app.
DATABASES['default'].update({
    'HOST': 'gitmanager',
})