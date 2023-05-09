# Django application settings

When deploying, overwrite necessary configurations in `gitmanager/local_settings.py`.

The application uses a database. If `sqlite3` is used (in `settings.py`), it must be installed:

    sudo apt-get install sqlite3 libsqlite3-dev

Django must install the database schema (Python virtual environment must be activated):

    python manage.py migrate


# Asynchronous builds (Huey)

To build courses synchronously with the HTTP requests, set `immediate` to `True`
in the `HUEY` dict in `gitmanager/local_settings.py`:

    HUEY["immediate"] = True

To build courses asynchronously from the HTTP requests, a separate builder
process and a message broker are need. The message broker is configured to be
redis by default but it can be changed in `gitmanager/local_settings.py`.
The redis connection parameters can also be set there, or you can specify
`REDIS_HOST` and `REDIS_PORT` environment variables (defaults to `localhost` and `6379`).
To run the builder process:

    python manage.py run_huey


# Course config caching

For performance reasons, you may want to enable an interprocess cache in the local_settings.py
`CACHES` setting. Memcached is a good option for this. You may need to increase the cache total and
object size for it to work properly. The default object size of 1MB will work fine for small to
medium size courses but larger courses may require more space, 5MB should be fine for all but the
most exceptional cases. The total size needed depends on the number of courses and their sizes,
a surefire way is to take the maximum object size and multiply it by the number of courses. Note
that you need to install the appropriate python package for the cache, see
https://docs.djangoproject.com/en/3.2/topics/cache/. The requirements_prod.txt file contains the
python package for memcached.

If a course build is stuck locked (can be seen in huey logs (repeated locked messages), and the
build is stuck in RUNNING and PENDING states), the task lock can be flushed with the flush_huye
django admin command.

# Disk storage considerations

Git manager uses three folders for storing courses called build, store and publish. The paths of
these folder can be set using the `BUILD_PATH`, `STORE_PATH`, and `COURSES_PATH` settings,
respectively. For performance and uptime reasons, os.rename must be supported between the store
and publish folders. On some Unix flavors this means that the two folders must be on the same
filesystem.

## Physical disk location

Large amount of disk I/O is expected during the build for large courses. It is highly recommended
to use a local disk (i.e. connected directly to the server) for the build folder for this reason.
If the local disk might change during restarts (e.g. in a kubernetes cluster), one should (to save
disk space) either manually delete the old build folder when the local disk changes (or on every
restart) or add a hook to do it automatically. This does mean that the course material must be
recloned from git afterwards but it is still generally faster to do that than to not use a local disk.

## Folder access

Only the Huey process needs access to the build folder while only the main django process needs
access to the publish folder. Both processes need access to the store folder.


# Custom build runners (running builds on something other than locally or on docker containers)

The python module used to run the course build scripts can be changed using the `BUILD_MODULE` setting.
The interface used can be found in the `scripts/build_template.py` file. The other two files in that
directory can be used as examples.

Custom settings can be passed to the build script using the `BUILD_MODULE_SETTINGS` setting.

The `scripts/docker_build.py` module is used to run the course build scripts in a docker container.
See the comment at the top of the file for the `BUILD_MODULE_SETTINGS` options.

The `scripts/local_build.py` module is used to run the course build scripts locally. Note that this
module does not support course build image and command options.