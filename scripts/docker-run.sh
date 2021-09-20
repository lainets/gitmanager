#!/bin/sh
image=$1
course_path=$2
host_course_path=$3
envs=$4

envstr=$(echo "$envs" | while IFS= read line; do echo "-e $line"; done | tr '\n' ' ')

set -e

# build the course material inside the tmp folder
docker run $envstr -v "$host_course_path:/content" --workdir "/content" $image
