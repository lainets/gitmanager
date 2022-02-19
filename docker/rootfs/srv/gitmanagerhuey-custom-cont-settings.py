# Use the local settings from the gitmanager web app
# with some modifications for the Huey worker (task queue consumer).
# Dockerfile.huey adds gitmanager-cont-settings.py to the start of this file.

# In the worker, COURSES_PATH does not need to be in the same device as STORE_PATH
# because the worker never writes to COURSES_PATH.
# The worker only copies the build output to STORE_PATH.
COURSES_PATH = '/srv/courseshuey'

# Connect to the database in the gitmanager web app.
DATABASES['default'].update({
    'HOST': 'gitmanager',
})