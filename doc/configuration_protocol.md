# Protocol used to configure exercise graders

The grader configuration happens in two stages: storing and publishing. In the
storing stage, gitmanager sends all the relevant files and configs to the grader
to be stored for later. Sometime after the storing, gitmanager will send another
request telling the grader to publish the stored course. The rationale is that
this way we can do all the heavy lifting before hand, and then publish the
changes to the course at once everywhere.

## Storing stage

Gitmanager will send a POST request with the following POST fields:
* `version_id`: an unique id for this config version
* `course_id`: the id of the course on A+
* `course_key`: the course key on gitmanager
* `course_spec`: the parsed contents of the course config file
* `exercises`: a list of
    * `key`: exercise key
    * `spec`: the exercise specification from the index.json/yaml file without
    the `configure` and `config` fields.
    * `config`: the parsed contents of the exercise's config file (specified in
    index.json/yaml) as a dictionary
    * `files`: paths of the files corresponding to this exercise in the TAR
    file explained below. Note that multiple exercises CAN share a file in the
    TAR.
and a single TAR file containing all the files.

The TAR file contains the files specified in the `configure` fields of the
index.json/yaml file. The path of each file is the key in `configure` and the
file is the file found from the value (a path) of said key.

The grader should respond with a JSON where the keys are the keys of exercises
and the value, for each exercise, is a dictionary of default configuration
values. Any field not specified in the course configuration will be set to
the value in this default configuration.

## Publishing stage

Gitmanager will send a POST request with the following POST fields:
* `version_id`: the unique id of the config version to be published
* `course_id`: the id of the course on A+
* `course_key`: the course key on gitmanager
* `publish`: true

If `version_id` does not match the `version_id` of the course currently
published or the one that is stored, the grader should leave the course as is
and return an error saying that the `version_id` does not match.

If succesful, the grader should respond with an empty response or a list of errors (in JSON).