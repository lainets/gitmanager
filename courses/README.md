Course and exercise configuration and build
=================================

## Build environment variables

The following environment variables are available to the build container:

- COURSE_KEY: the Git Manager specific course key. E.g. aplus_manual_master or
c1234_2021
- COURSE_ID: database id of the course on A+. E.g. 142
- STATIC_URL_PATH: URL to the course static files (no host or scheme).
E.g. /static/default or /static/aplus_manual_master
- STATIC_CONTENT_HOST: full static file URL (including scheme and host).
E.g. https://gitmanager.cs.aalto.fi/static/default

## Configuration files

Configuration is written as JSON or YAML inside subdirectories.
Each subdirectory holding an `index.json` or `index.yaml` is a
valid active course.

Dates will be parsed as '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S',
'%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d %H' or '%Y-%m-%d'.
Durations are given in (int)(unit), where units are y, m, d, h or w.

1. ## apps.meta
	* `grader_config`: where to find course configuration files, defaults to
	the course root folder
	* `build_image`: container image used to build the course, defaults to a
	value set by the service administrators.
	* `build_cmd`: command passed to the container image above. If not specified,
	the image default is used.
	* `exlude_patterns`: a list of exclude patterns for paths to ignore when cleaning the git directory. E.g. `exclude_patterns = _build exercises` makes sure that _build and exercises folders that were left over from last build are not removed before rebuilding. See git clean command's exclude flag for more information.

2. ### <grader_config>/index.[json|yaml]
	* The directory name acts as a course key, which is used in
		* URLs: `/course_key`
	* `name`: A public complete course name
	* `description` (optional): A private course description
	* `lang` (optional/a+): The default language.
	* `contact`: (optional/a+) A private contact email for course configuration
	* `contact_phone`: (optional) A private contact phone number for course responsible
	* `assistants`: (optional/a+) A list of assistant student ids
	* `start`: (optional/a+) The course instance start date
	* `end`: (optional/a+) The course instance end date
	* `static_dir`: (optional) This subdirectory will be linked to URL /static/course_key
	* `head_urls`: (optional/a+) A list of URLs to JS and CSS files that A+ includes
		on all course pages. For example, a common JavaScript library could be included
		this way without adding it separately to each exercise description.
	* `enrollment_start`: The enrollment start date
	* `enrollment_end`: The enrollment end date
	* `lifesupport_time`: The lifesupport date (model answers are hidden from students)
	* `archive_time`: The archive date (no submissions allowed after it)
	* `enrollment_audience`: Selects the user group that is allowed to enroll in the course. One of the following:
		* `internal`: only internal students
		  (they have a student number and should log-in with internal accounts)
		* `external`: only external students (no student number and login with Google accounts)
		* `all`: internal and external students
	* `view_content_to`: Selects the user group that may view course contents. One of the following:
		* `enrolled`: only enrolled students
		* `enrollment_audience`: logged-in users in the enrollment audience (the audience is set separately)
		* `all_registered`: all logged-in users
		* `public`: all anonymous and authenticated users
	* `index_mode`: Selects the display mode for the course front page. One of the following:
		* `results`: exercise results
		* `toc`: table of contents
		* `last`: opens the page that the user viewed last time
		* `experimental`: do not use this
	* `content_numbering`: numbering mode for the course contents (chapters and exercises). One of the following:
		* `none`: no numbers shown
		* `arabic`: arabic numbers (1, 2, 3)
		* `roman`: roman numbers (I, II, III)
		* `hidden`: no numbers, but child objects may show the hierarchy in numbering.
			If there are children (e.g., exercises are children of the module) and
			the parent has hidden numbering, then the children may have numbers
			such as "1.2" instead of just "2" (exercise 2 in the round 1).
			The hidden setting is more sensible in `module_numbering` than `content_numbering`.
	* `module_numbering`: numbering mode for the modules (exercise rounds).
		The options are the same as for `content_numbering`.
	* `course_description`: HTML text for the course front page
	* `course_footer`: HTML text for the footer of the front page
	* `configures`: list of external configuration settings. A list of
		* `url`: where to send the course configuration (optional).
		If missing, the service uses the default grader configured by the server admins.
		* `files`: what files to send. A dict of `<name>: <path>`
		pairs. The file/directory at `<path>` is sent to the url with
		the name `<name>`.
	* `exercises`: (deprecated, see modules) A list of active exercise keys
	* `modules`: a list of
		* `key`: part of the url
		* `name`,`title`: (optional/a+) The name of the course module
		* `order`: (optional/a+) the order number of the module
		* `status`: (optional/a+) ready/hidden/maintenance
		* `points_to_pass`: (optional/a+) limit to get passed marks
		* `introduction`: (optional/a+) introduction
		* `open`: (optional/a+) first access date
		* `close`: (optional/a+) deadline date
		* `duration`: (optional/a+) deadline in duration from open
		* `read-open`: (optional/a+) module reading opening time
		* `late_close`: (optional/a+) late deadline date
		* `late_duration`: (optional/a+) late deadline in duration from first deadline
		* `late_penalty`: (optional/a+) factor of points worth for late submission
		* `type`: (optional/a+) a key name in 'module_types'
		* `children`: a list of
			* `key`: part of the url
			* `name`,`title`: (optional/a+) The name of the learning object
			* `category`: a key name in 'categories'
			* `status`: (optional/a+) ready/unlisted/hidden/maintenance
			* `audience`: (optional/a+) the audience on A+. One of the following:
				* `internal`: only internal students
				(they have a student number and should log-in with internal accounts)
				* `external`: only external students (no student number and login with Google accounts)
				* `all`: internal and external students
			* `order`: (optional/a+) the order number of the exercise
			* `model_answer`
			* `exercise_template`
			* `exercise_info`
			* `url`: (optional*/a+) where to find the exercise/chapter,
			optional for chapters
			* `use_wide_column`: (optional/a+) true to loose third column
			* `description`: (optional/a+) exercise description
			* `type`: (optional/a+) a key name in 'exercise_types'
			* `children`: (optional/a+) list recursion
			* Extended with of these:
			* Chapter:
				* `static_content`: a localized path to the static content directory
				* `generate_table_of_contents`: (optional/a+) whether to
				generate the table of contents
			* Exercise:
				* `config`: (optional) a path to exercise configuration. Must
				be either a json or a yaml file. See <grader_config>/<config path>
				specification below.
				* `max_submissions`: (optional/a+)
				* `max_points`: (optional/a+)
				* `points_to_pass`: (optional/a+) limit to get passed marks
				* `min_group_size`: (optional/a+)
				* `max_group_size`: (optional/a+)
				* `allow_assistant_viewing`: (optional/a+) true or false
				* `allow_assistant_grading`: (optional/a+) true or false
				* `generate_table_of_contents`: (optional/a+) show index of children
				* `configure`: external configuration settings
					* `url`: where to send the exercise configuration (optional).
					If missing, the service uses the default grader configured by the server admins.
					* `files`: what files to send. A dict of `<name>: <path>`
					pairs. The file/directory at `<path>` is sent to the url with
					the name `<name>`.
			* LTI exercise (extends Exercise):
				* `lti`: the label used in A+ for the LTI service
				* `lti_context_id`: LTI context id
				* `lti_resource_link_id`: LTI resource link id
				* `lti_aplus_get_and_post`: whether to perform GET and POST
				from A+ to custom service URL with LTI data appended
				* `lti_open_in_iframe`: whether to open the exercise in an iframe
			* Exercise collection:
				* `target_category`: the category name of the collection
				* `target_url`: URL of the course instance
				* `max_points`: maximum points given
				* `points_to_pass`: (optional/a+) points needed to pass
	* `categories`: a dict where the key is the category key and value is a dict
		* `name`: name of the category
		* `status`: (optional/a+) ready/hidden
		* `description`: (optional/a+)
		* `points_to_pass`: (optional/a+) limit to get passed marks
		* `confirm_the_level`: (optional/a+) whether a user must have more than
		0 points in this category before their other points in the same
		chpater/module become confirmed
		* `accept_unofficial_submits`: (optional/a+) whether to allow more
		submissions after deadline/max submission count is exceeded. The points
		given in those cases will not officially count.
	* `module_types`,`exercise_types`: keyed maps of default values
	* `numerate_ignoring_modules`: (optional/a+) true to numerate I:1...n, II:n+1...m

3. ### `<grader_config>/<config path>`

This file must end in `.json` or `.yaml`, and be in the respective format.
`<config path>` may omit the filename extension.

* The file name acts as an exercise key, which is used in
	* URLs: `/course_key/exercise_key`
	* Must match the exercise list in `index.[json|yaml]`
* May override the following fields from the exercise config specified in index.json/yaml:
	* `name`, `title`
	* `description`
	* `url`
	* `exercise_info`
	* `model_answer`
	* `exercise_template`
* `include` (optional): Include configuration files rendered from templates.
	* `file`: A path to an exercise configuration file. May contain optional Django template syntax, which allows passing of parameters with the `template_context` key.
	* `force` (optional): Defaults to false. If true, all keys and their contents in the file where the `include` key is located will be overwritten with the corresponding keys and contents from the file which is being included. If false, a ConfigError is thrown if the include file contains keys which already exist in the file where the keys are being included.
	* `template_context` (optional): Context dictionary containing key value pairs for rendering the included file.
* `instructions_file` (optional) (DEPRECATED): A path to a file that will be automatically added to the configuration files list.
If the path starts with `./`, it will be prepended with the course key.
DEPRECATION: Sometime in the future, this file will not be added automatically.
* `model_files` (optional): It is a list of model answers that are available only after the deadline has passed. Possibly overrides `model_answer`, see Precedence below.
The `model_files` take file paths as input. These paths are relative to the root of the course repository,
e.g., `exercises/hello_world/model.py`.
* `template_files` (optional): List of template files for the student (e.g., base code or skeleton code that the student starts to modify). Possibly overrides `exercise_template`, see Precedence below.
A+ shows the templates in the exercise navigation bar.
Give a list of file paths as the value. The file paths start from the root of the course repository,
e.g., `exercises/hello_world/submission.py`.
* Any additional fields needed by the grading service

#### Precedence for `model_answer` and `exercise_template`

The precedence order for `model_answer` and `exercise_template` is as follows:
1. `model_answer`/`exercise_template` in course_key/exercise_key.[json|yaml]
2. `model_files`/`template_files` in course_key/exercise_key.[json|yaml]
3. `model_answer`/`exercise_template` in course_key/index.[json|yaml]
