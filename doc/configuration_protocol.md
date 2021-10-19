# Protocol used to configure exercise graders

Gitmanager will send a POST request with the following POST fields:
* `course_id`: the id of the course on A+
* `course_key`: the course key on gitmanager
* `exercises`: a list of
    * `key`: exercise key
    * `spec`: the exercise specification from the index.json/yaml file without
    the `configure` and `config` fields.
    * `config`: the parsed contents of the exercise's config file (specified in
    index.json/yaml) as a dictionary
    * `files`: paths of the files corresponding to this exercise in the ZIP
    file explained below. Note that multiple exercises CAN share a file in the
    ZIP.
and a single ZIP file containing all the files.

The ZIP file contains the files specified in the `configure` fields of the
index.json/yaml file. The path of each file is the key in `configure` and the
file is the file found from the value (a path) of said key.

The grader should respond with a JSON where the keys are the keys of exercises
and the value, for each exercise, is a dictionary of default configuration
values. Any field not specified in the course configuration will be set to
the value in this default configuration.
