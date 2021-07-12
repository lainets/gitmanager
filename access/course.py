from typing import Any, Dict, Optional, List, Union
from datetime import datetime, timedelta

from pydantic import BaseModel as PydanticModel, Field

from util.localize import Localized, DEFAULT_LANG


class Parent(PydanticModel):
    children: List[Union["Chapter", "Exercise"]] = []


class Item(Parent):
    key: str
    category: str
    status: Optional[str]
    order: Optional[int]
    audience: Optional[str]
    name: Optional[Localized[str]]
    description: Optional[str]
    use_wide_column: Optional[bool]
    url: Optional[Localized[str]]
    model_answer: Optional[Localized[str]]
    exercise_template: Optional[Localized[str]]
    exercise_info: Optional[Any]

    @root_validator(allow_reuse=True, pre=True)
    def name_or_title(cls, values: Dict[str, Any]):
        if "name" in values and "title" in values:
            raise ValueError("Only one of name and title should be specified")
        if "title" in values:
            values["name"] = values.pop("title")
        return values


class Exercise(Item):
    allow_assistant_viewing: Optional[bool]
    allow_assistant_grading: Optional[bool]
    config: Optional[str]
    type: Optional[str]
    confirm_the_level: Optional[bool]
    difficulty: Optional[str]
    min_group_size: Optional[int]
    max_group_size: Optional[int]
    max_points: Optional[int]
    max_submissions: Optional[int]
    points_to_pass: Optional[int]

    class Config:
        extra = "forbid"


class Chapter(Item):
    static_content: Localized[str]
    generate_table_of_contents: Optional[bool]

    class Config:
        extra = "forbid"


Parent.update_forward_refs()
Exercise.update_forward_refs()
Chapter.update_forward_refs()


class SimpleDuration(PydanticModel):
    __root__: str

    @root_validator(allow_reuse=True, pre=True)
    def simple_duration(cls, delta: Any):
        if not isinstance(delta, str):
            raise ValueError("A duration must be a string")
        if not len(delta) > 0:
            raise ValueError("An empty string cannot be turned into a duration")

        try:
            int(delta[:-1])
        except:
            raise ValueError("Format: <integer>(y|m|d|h|w) e.g. 3d")

        if delta[-1] in ("y", "m", "w", "d", "h"):
            return delta
        else:
            raise ValueError("Format: <integer>(y|m|d|h|w) e.g. 3d")


class Module(Parent):
    name: Localized[str]
    key: str
    status: str
    order: Optional[int]
    introduction: Optional[str]
    open: Optional[datetime]
    close: Optional[datetime]
    duration: Optional[Union[timedelta, SimpleDuration]]
    read_open: Optional[datetime] = Field(alias="read-open")
    points_to_pass: Optional[int]
    late_close: Optional[datetime]
    late_penalty: Optional[float]
    late_duration: Optional[Union[timedelta, SimpleDuration]]
    numerate_ignoring_modules: Optional[bool]

    @root_validator(allow_reuse=True, pre=True)
    def name_or_title(cls, values: Dict[str, Any]):
        if "name" in values and "title" in values:
            raise ValueError("Only one of name and title should be specified")
        if "title" in values:
            values["name"] = values.pop("title")
        return values

class Course(PydanticModel):
    name: str
    modules: List[Module]
    lang: Union[str, List[str]] = DEFAULT_LANG
    archive_time: Optional[datetime]
    assistants: Optional[List[str]]
    categories: Dict[str, Any] = {} # TODO: add a pydantic model for categories
    contact: Optional[str]
    content_numbering: Optional[str]
    course_description: Optional[str]
    course_footer: Optional[str]
    description: Optional[str]
    start: Optional[datetime]
    end: Optional[datetime]
    enrollment_audience: Optional[str]
    enrollment_end: Optional[datetime]
    enrollment_start: Optional[datetime]
    head_urls: List[str] = []
    index_mode: Optional[str]
    lifesupport_time: Optional[datetime]
    module_numbering: Optional[str]
    numerate_ignoring_modules: Optional[bool]
    view_content_to: Optional[str]
    static_dir: Optional[str]
