FROM --platform=$TARGETPLATFORM apluslms/service-base:django-1.18

# Set container related configuration via environment variables.
ENV CONTAINER_TYPE="gitmanager" \
    GITMANAGER_LOCAL_SETTINGS="/srv/gitmanager-cont-settings.py" \
    GITMANAGER_SECRET_KEY_FILE="/local/gitmanager/secret_key.py" \
    REDIS_HOST="redis" \
    HUEY_IMMEDIATE="true"

ARG TARGETPLATFORM

RUN : \
 && apt_install \
      apt-transport-https \
      rsync \
      # temp
      gnupg curl \
  # install docker-ce
 && if [ "$TARGETPLATFORM" = "linux/amd64" ] ; then ARCH=amd64 ; elif [ "$TARGETPLATFORM" = "linux/arm64" ] ; then ARCH=arm64 ; else exit 1 ; fi \
 && curl -LSs https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg >/dev/null 2>&1 \
 && echo "deb [arch=$ARCH signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian bullseye stable" > /etc/apt/sources.list.d/docker.list \
 && apt_install docker-ce \
\
  # create user
 && adduser --system --no-create-home --disabled-password --gecos "Git Manager webapp server,,," --home /srv/gitmanager --ingroup nogroup gitmanager \
 && mkdir /srv/gitmanager && chown gitmanager.nogroup /srv/gitmanager \
 && rm -rf /etc/init.d/ /tmp/* \
  # database settings that allow the Huey worker container to connect to the gitmanager web app's database
 && find /etc/postgresql/*/*/ -type f -name pg_hba.conf -exec sh -c 'echo "host all all samenet trust" >> "$1"' -- {} \; \
 && find /etc/postgresql/*/*/ -type f -name postgresql.conf -exec sed -i "s/listen_addresses = ''/listen_addresses = '*'/" {} \; \
 && apt_purge \
      gnupg curl \
 && :

COPY docker/rootfs /
COPY . /srv/gitmanager

RUN cd /srv/gitmanager \
  # prebuild .pyc files
 && python3 -m compileall -q . \
  # install requirements, remove the file, remove unrequired locales and tests
 && pip_install -r requirements.txt \
 && rm requirements.txt \
 && find /usr/local/lib/python* -type d -regex '.*/locale/[a-z_A-Z]+' -not -regex '.*/\(en\|fi\|sv\)' -print0 | xargs -0 rm -rf \
 && find /usr/local/lib/python* -type d -name 'tests' -print0 | xargs -0 rm -rf \
\
 && export \
    GITMANAGER_SECRET_KEY="-" \
 && python3 manage.py compilemessages 2>&1 \
\
  # default course directory
 && mkdir -p /srv/courses/ \
 && mkdir -p /srv/courses/default \
 && mkdir -p /srv/course_store \
 && chown -R gitmanager.nogroup \
    /srv/courses \
    /srv/course_store \
    /srv/gitmanager \
\
  # clean
 && rm -rf $GITMANAGER_SECRET_KEY_FILE \
 && rm -rf /etc/init.d/ /tmp/* \
 && :


VOLUME /srv/courses
WORKDIR /srv/gitmanager/
EXPOSE 8070
CMD [ "manage", "runserver", "0.0.0.0:8070" ]
