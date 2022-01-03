* For installation, see /README.md
* For exercise configuration, see /courses/README.md

# Gitmanager Filesystem Walkthrough

* `/doc`: Description of the system and material for system administrators.

* `/gitmanager`: Django project settings, urls and wsgi accessor.

* `/templates`: Base templates for default grader pages.

* `/static`: Static files for default grader pages.

* `/access`: Django application presenting courses.

	* `templates`: View templates.

	* `types`: Implementations for different exercise view types.

	* `management`: Commandline interface for testing configured exercises.

* `/util`: Utility modules for HTTP, shell, filesystem access etc.

* `/courses`: Default COURSES_PATH for holding course exercise configuration and material.

* `/course_store`: Default STORE_PATH for temporarily storing built course exercise configuration and material.

* `/scripts`: Python modules for different types of builders.
