#!/bin/sh
image=$1
course_path=$2
host_course_path=$3

set -e

# build the course material inside the tmp folder
docker run -v "$host_course_path:/content" --workdir "/content" $image
