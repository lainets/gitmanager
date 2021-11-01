'''
Utility functions for exercise files.

'''
from typing import Any, Dict, Generator, Iterable, Tuple, Union
from django.conf import settings
import datetime, random, string, os, shutil, json
from pathlib import Path

from util.typing import PathLike


META_PATH = os.path.join(settings.SUBMISSION_PATH, "meta")
if not os.path.exists(META_PATH):
    os.makedirs(META_PATH)


def read_meta(file_path: PathLike) -> Dict[str,str]:
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


def is_subpath(child: str, parent: str):
    if child == parent:
        return True
    return len(child) > len(parent) and child[len(parent)] == "/" and child.startswith(parent)


def file_mappings(root: Path, mappings_in: Iterable[Tuple[str,str]]) -> Generator[Tuple[str, Path], None, None]:
    """
    Resolves (name, path) tuples into (name, file) tuples.
    E.g. if path is a folder, we get an entry for each file in it.

    Raises ValueError if a name has multiple different files.
    """
    mappings = sorted((name, root / path) for name, path in mappings_in)

    def in_course_dir_check(path: Path):
        nonlocal root
        try:
            path.resolve().relative_to(root)
        except:
            raise ValueError(f"{path} links outside the course directory")

    def expand_dir(name: str, path: Path) -> Generator[Tuple[str,Path], None, None]:
        for child in path.iterdir():
            child_name = name / child.relative_to(path)
            yield str(child_name), child

    def expand_full(name: str, path: Path) -> Generator[Tuple[str,Path], None, None]:
        if path.is_file():
            in_course_dir_check(path)
            yield name, path
        elif path.is_dir():
            for root, _, files in os.walk(path, followlinks=True):
                root = Path(root)
                rootname = name / root.relative_to(path)
                for file in files:
                    in_course_dir_check(root / file)
                    yield str(rootname / file), root / file

    while mappings:
        while len(mappings) > 1 and is_subpath(mappings[1][0], mappings[0][0]):
            map = mappings.pop(0)
            if map[1].is_file():
                if map[0] != mappings[0][0]:
                    raise ValueError(f"{map[0]} is mapped to a file ({map[1]}) but {mappings[0][0]} is under it")
                elif map[1] != mappings[0][1]:
                    raise ValueError(f"{map[0]} is mapped to a file {map[1]} and the path {mappings[0][1]}")
            elif map[1].is_dir():
                mappings.extend(expand_dir(*map))
                mappings.sort()

        yield from expand_full(*mappings.pop(0))