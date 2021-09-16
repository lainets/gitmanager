'''
Utility functions for exercise files.

'''
from typing import Any, Dict, Union
from django.conf import settings
import datetime, random, string, os, shutil, json
from pathlib import Path


META_PATH = os.path.join(settings.SUBMISSION_PATH, "meta")
if not os.path.exists(META_PATH):
    os.makedirs(META_PATH)


def read_meta(file_path: Union[str, bytes, "os.PathLike[Any]"]) -> Dict[str,str]:
    '''
    Reads a meta file comprised of lines in format: key = value.

    @type file_path: C{str}
    @param file_path: a path to meta file
    @rtype: C{dict}
    @return: meta keys and values
    '''
    meta: Dict[str,str] = {}
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            for key,val in [l.split('=') for l in f.readlines() if '=' in l]:
                meta[key.strip()] = val.strip()
    return meta


def rm_path(path: Union[str, Path]) -> None:
    path = Path(path)
    if path.is_symlink():
        path.unlink()
    elif not path.exists():
        return
    elif path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def zip_dir(ziph: ZipFile, path: Path, name: str = None) -> None:
    if name is None:
        name = path.name

    for root, _, files in os.walk(path):
        root = Path(root)
        rootname = name / root.relative_to(path)
        for file in files:
            ziph.write(root / file, rootname / file)


def zip_path(ziph: ZipFile, path: Path, name: str = None) -> None:
    if name is None:
        name = path.name

    if path.is_dir():
        zip_dir(ziph, path, name)
    elif path.is_file() and not path.is_symlink():
        ziph.write(path, name)
