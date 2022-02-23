# run-gitmanager container

Docker container for local development and testing of the Git Manager.

There are separate Dockerfiles for the gitmanager web app and the Huey worker
container (course builder).

Building the images (from the gitmanager repo root):
* `docker build -t apluslms/run-gitmanager:latest -f docker/Dockerfile .`
* `docker build -t apluslms/run-gitmanager-huey:huey-latest --build-arg FULL_TAG=latest -f docker/Dockerfile.huey .`

`Dockerfile.huey` uses `run-gitmanager` as the base image.
The build argument `FULL_TAG` defines the image tag of the base image.

## Docker Compose file examples

These may be used in an A+ course directory or repository such as aplus-manual.
Rename the file to `docker-compose.yml`.

* `docker-compose_no-gitmanager.yml`: a-plus and mooc-grader without gitmanager
* `docker-compose-immediate.yml`: a-plus, mooc-grader and gitmanager
  in the Huey immediate mode (no build task queue)
* `docker-compose-full.yml`: a-plus, mooc-grader, gitmanager and Huey worker
  for building the course

The gitmanager source code may be mounted to `/srv/gitmanager` or
`/src/gitmanager` for testing changes in the code.
The same code should be mounted to both gitmanager and huey containers.

* `/srv/gitmanager`: Django reloads changes in the Python source code files
  without restarting the container.
* `/src/gitmanager`: The container copies the code to `/srv/gitmanager` at startup.
  The container compiles the translated messages automatically.

## Git Manager tests

Git Manager unit tests can be run with this Docker Compose file:
`docker-compose-tests.yml`.
