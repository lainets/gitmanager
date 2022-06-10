# gitmanager

Gitmanager is a service for building and validating courses, and configuring
other services in the A+ ecosystem. The courses are loaded through git, and then
automatically built inside a configurable container. If the build passes
validation, the course and its exercises are configured on A+ and compatible
grading services.

The application is implemented on Django 3.2 (`gitmanager/settings.py`) and
requires Python 3.7+.

Gitmanager can be run stand alone without the full stack to test any part of
the process in the local system environment. Course and exercise
configuration is in COURSES_PATH directory (defaults to `courses`) once built and published.

Course files are downloaded using git to the BUILD_PATH directory, where the
course is then built. If the build is successfull, the course directory is then
copied to the STORE_PATH directory. That directory is solely for storage, that
version of the course is not available until the course is published. The course
is published by A+ when A+ fetches and updates the course configuration. Once
the course is published, the built course is copied from the STORE_PATH directory
to the COURSES_PATH directory.

## Installing for development

You may run the app with Docker without installing the whole software stack locally.
It is easy to get started with the aplus-manual course:
[apluslms/aplus-manual](https://github.com/apluslms/aplus-manual).
The dockerfile in .github/workflows should contain everything needed to run
the application.

### Ubuntu 20.04

#### 1. Clone the software

General requirements

    sudo apt-get install git libjpeg-dev
    sudo apt-get install libxml2-dev libxslt-dev zlib1g-dev

Install software

    git clone https://github.com/apluslms/gitmanager.git

#### 2. Python requirements

    sudo apt-get install python3 python3-dev python3-pip python3-venv

Then, create virtual environment with gitmanager requirements.

    python3 -m venv venv
    source venv/bin/activate
    pip install wheel
    pip install -r gitmanager/requirements.txt

#### 3. Running the gitmanager application

Run the Django app locally:

    cd gitmanager
    python manage.py runserver

#### 4. For configuring courses and exercises, see

[courses/README.md](courses/README.md)

## Installing the full stack

### Ubuntu 20.04

#### 0. User account

On a server, one can install gitmanager for a specific gitmanager
user account.

    sudo adduser --system --group \
      --shell /bin/bash --home /srv/gitmanager \
      --gecos "A-plus gitmanager service" \
      gitmanager
    su - gitmanager

**Then follow the "Installing for development" and continue from here.**

#### 1. Web server configuration

##### Create temporary directory for sockets

    echo "d /run/gitmanager 0750 gitmanager www-data - -" | \
      sudo tee /etc/tmpfiles.d/gitmanager.conf > /dev/null
    sudo systemd-tmpfiles --create


Install uwsgi to run WSGI processes. The **gitmanager directory
and user must** be set in the configuration files.

##### uWSGI with systemd (Ubuntu >= 15.04)

    source ~/venv/bin/activate
    pip install uwsgi
    cp ~/gitmanager/doc/etc-uwsgi-gitmanager.ini ~/gitmanager-uwsgi.ini
    sudo cp ~/gitmanager/doc/etc-systemd-system-uwsgi.service /etc/systemd/system/gitmanager-uwsgi.service
    # EDIT ~/gitmanager-uwsgi.ini
    # EDIT /etc/systemd/system/gitmanager-uwsgi.service, set the correct uwsgi path to ExecStart

Operate the workers:

    # as root
    systemctl status gitmanager-uwsgi
    systemctl start gitmanager-uwsgi
    systemctl enable gitmanager-uwsgi  # start on boot
    # Graceful application reload
    touch ~/gitmanager-uwsgi.ini

##### nginx

    apt-get install nginx
    sed -e "s/__HOSTNAME__/$(hostname)/g" \
      ~/gitmanager/doc/etc-nginx-sites-available-gitmanager > \
      /etc/nginx/sites-available/$(hostname).conf
    ln -s ../sites-available/$(hostname).conf /etc/nginx/sites-enabled/$(hostname).conf
    # Edit /etc/nginx/sites-available/$(hostname).conf if necessary
    # Check nginx config validity
    nginx -t
    systemctl reload nginx

##### apache2

    apt-get install apache2 libapache2-mod-uwsgi
    # Configure based on doc/etc-apache2-sites-available-gitmanager
    a2enmod headers

## Django application settings for deployment

When deploying, overwrite necessary configurations in `gitmanager/gitmanager/local_settings.py`.

The application uses a database. If `sqlite3` is used (in `settings.py`), it must be installed:

    sudo apt-get install sqlite3 libsqlite3-dev

Django must install the database schema (Python virtual environment must be activated):

    python manage.py migrate

To build courses synchronously with the HTTP requests, set `immediate = True`
in the `HUEY` dict in `gitmanager/gitmanager/local_settings.py`.

To build courses asynchronously from the HTTP requests, a separate builder
process and a message broker are need. The message broker is configured to be
redis by default but it can be changed in `gitmanager/gitmanager/local_settings.py`.
The redis connection parameters can also be set there, or you can specify
`REDIS_HOST` and `REDIS_HOST` environment variables. To run the builder process:

    python manage.py run_huey

For performance reasons, you may want to enable an interprocess cache in the settings.py `CACHES`
setting. Memcached is a good option for this. You may need to increase the cache total and
object size for it to work properly. The default object size of 1MB will work fine for small to
medium size courses but larger courses may require more space, 5MB should be fine for all but the
most exceptional cases. The total size needed depends on the number of courses and their sizes,
a surefire way is to take the maximum object size and multiply it by the number of courses. Note 
that you need to install the appropriate python package for the cache, see 
https://docs.djangoproject.com/en/3.2/topics/cache/. The requirements_prod.txt file contains the
python package for memcached.
