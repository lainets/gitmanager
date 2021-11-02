from itertools import chain
import json
from json.decoder import JSONDecodeError
import logging
from pathlib import Path
from tempfile import TemporaryFile
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
from tarfile import PAX_FORMAT, TarFile

from aplus_auth.payload import Permission, Permissions
from aplus_auth.requests import Session
from requests.models import Response
from requests.packages.urllib3.util.retry import Retry
from requests.sessions import HTTPAdapter
from requests_toolbelt.multipart.encoder import MultipartEncoder

from access.config import CourseConfig
from access.course import Exercise
from gitmanager.models import Course
from util.export import JSONEncoder
from util.files import file_mappings


logger = logging.getLogger("gitmanager.configure")


def configure_url(
        url: str,
        course_id: int,
        course_key: str,
        dir: str,
        files: Iterable[Tuple[str, str]],
        **kwargs: Any
        ) -> Tuple[Optional[Response], Optional[Union[str, Dict[str,str]]]]:

    logger.debug(f"Compressing for {url}")

    tmp_file = TemporaryFile(mode="w+b")
    # no compression, only pack the files into a single package
    tarh = TarFile(mode="w", fileobj=tmp_file, format=PAX_FORMAT)

    try:
        for name, path in file_mappings(Path(dir), files):
            tarh.add(path, name)
    except ValueError as e:
        return None, f"Skipping {url} configuration: error in zipping files: {e}"

    tarh.close()
    tmp_file.seek(0)

    permissions = Permissions()
    permissions.instances.add(Permission.WRITE, id=course_id)

    data_dict = {
        "course_id": str(course_id),
        "course_key": course_key,
        "files": ("files", tmp_file, "application/octet-stream"),
        **{
            k: v if isinstance(v, str) else json.dumps(v, cls=JSONEncoder)
            for k,v in kwargs.items()
        },
    }
    data = MultipartEncoder(data_dict)

    logger.debug(f"Configuring {url}")
    try:
        with Session() as session:
            retry = Retry(
                total=5,
                connect=5,
                read=2,
                status=3,
                allowed_methods=None,
                status_forcelist=[500,502,503,504],
                raise_on_status=False,
                backoff_factor=0.4,
            )
            session.mount(url, HTTPAdapter(max_retries=retry))

            headers = {"Prefer": "respond-async", "Content-Type": data.content_type}
            response = session.post(url, headers=headers, data=data, permissions=permissions)
    except Exception as e:
        logger.warn(f"Failed to configure: {e}")
        return None, {"url": url, "error": f"Couldn't access {url}"}
    else:
        if response.status_code != 200:
            logger.warn(f"Failed to configure {url}: {response.status_code}\nResponse: {response.text}")
            return response, {"url": url, "code": response.status_code, "error": response.text}
    return response, None


def configure_graders(config: CourseConfig):
    course_key = config.key

    configures: Dict[str, Tuple[Dict[str,str], List[Exercise]]] = {}
    for conf in config.data.configures:
        url = conf.url
        configures[url] = (conf.files,[])

    for exercise in config.exercises.values():
        conf = exercise.configure
        if not conf:
            continue
        url = conf.url
        if url not in configures:
            configures[url] = ({},[])
        configures[url][1].append(exercise)

    course_id: int = Course.objects.get(key=course_key).remote_id

    if course_id is None and configures:
        raise ValueError("Remote id not set: cannot configure")

    course_spec = config.data.dict(exclude={"static_dir", "configures"})

    exercise_defaults: Dict[str, Any] = {}
    errors = []
    for url, (course_files, exercises) in configures.items():
        exercise_data: List[Dict[str, Any]] = []
        for exercise in exercises:
            exercise_data.append({
                "key": exercise.key,
                "spec": exercise.dict(exclude={"config", "configure"}),
                "config": exercise._config_obj.data if exercise._config_obj else None,
                "files": list(exercise.configure.files.keys()),
            })

        files = chain.from_iterable((
            course_files.items(),
            *(
                exercise.configure.files.items()
                for exercise in exercises
            )
        ))

        response, error = configure_url(url, course_id, course_key, config.dir, files, course_spec=course_spec, exercises=exercise_data)
        if error is not None:
            errors.append(error)

        if response is not None and response.status_code == 200:
            if not response.text and exercises:
                logger.warn(f"{url} returned an empty response on exercise configuration")
                errors.append(f"{url} returned an empty response on exercise configuration")
            else:
                try:
                    logger.debug(f"Loading from {url}")
                    defaults = json.loads(response.text)
                except JSONDecodeError as e:
                    logger.info(f"Couldn't load configure response:\n{e}")
                    logger.debug(f"{url} returned {response.text}")
                    errors.append({"url": url, "error": str(e)})
                else:
                    exercise_defaults = {
                        exercise.key: defaults[exercise.key]
                        for exercise in exercises
                        if exercise.key in defaults
                    }

    return exercise_defaults, errors