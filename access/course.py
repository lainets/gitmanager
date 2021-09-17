from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from datetime import datetime, timedelta

from pydantic import AnyHttpUrl, Field
from pydantic.class_validators import root_validator, validator
from pydantic.types import NonNegativeInt, PositiveInt, confloat

from util.localize import Localized, DEFAULT_LANG
from util.pydantic import PydanticModel, NotRequired

class Parent(PydanticModel):
    children: List[Union["Chapter", "Exercise", "LTIExercise", "ExerciseCollection"]] = []

    def child_categories(self) -> Set[str]:
        """Returns a set of categories of children recursively"""
        categories: Set[str] = set()
        for c in self.children:
            categories.add(c.category)
            categories.union(c.child_categories())
        return categories


class Item(Parent):
    key: str
    category: str
    status: NotRequired[str]
    order: NotRequired[int]
    audience: NotRequired[str]
    name: NotRequired[Localized[str]]
    description: NotRequired[str]
    use_wide_column: NotRequired[bool]
    url: NotRequired[Localized[str]] # TODO: url check
    model_answer: NotRequired[Localized[str]]  # TODO: url check
    exercise_template: NotRequired[Localized[str]] # TODO: url check
    exercise_info: NotRequired[Any] # TODO: json check

    class Config:
        extra = "forbid"

    @root_validator(allow_reuse=True, pre=True)
    def name_or_title(cls, values: Dict[str, Any]):
        if "name" in values and "title" in values:
            raise ValueError("Only one of name and title should be specified")
        if "title" in values:
            values["name"] = values.pop("title")
        return values

    @root_validator(allow_reuse=True, pre=True)
    def remove_fields(cls, values: Dict[str, Any]):
        values = {k:v for k,v in values.items() if k[0] != "_"}
        # DEPRECATED: scale_points exists for some reason in some index.yaml
        # it isn't used anywhere though. It should be removed altogether
        values.pop("scale_points", None)
        return values


class Exercise(Item):
    max_submissions: NonNegativeInt = 0
    allow_assistant_viewing: NotRequired[bool]
    allow_assistant_grading: NotRequired[bool]
    config: NotRequired[Path]
    type: NotRequired[str]
    confirm_the_level: NotRequired[bool]
    difficulty: NotRequired[str]
    min_group_size: NotRequired[NonNegativeInt]
    max_group_size: NotRequired[NonNegativeInt]
    max_points: NotRequired[NonNegativeInt]
    points_to_pass: NotRequired[NonNegativeInt]

    @root_validator(allow_reuse=True, skip_on_failure=True)
    def validate_assistant_permissions(cls, values: Dict[str, Any]):
        if not values.get("allow_assistant_viewing", False) and values.get("allow_assistant_grading", True):
            raise ValueError("Assistant grading is allowed but viewing is not")
        return values


class LTIExercise(Exercise):
    lti: str
    lti_context_id: NotRequired[str]
    lti_resource_link_id: NotRequired[str]
    lti_aplus_get_and_post: NotRequired[bool]
    lti_open_in_iframe: NotRequired[bool]


class ExerciseCollection(Item):
    target_category: str
    target_url: str
    max_points: PositiveInt
    points_to_pass: NotRequired[NonNegativeInt]


class Chapter(Item):
    static_content: Localized[Path]
    generate_table_of_contents: NotRequired[bool]

    @validator('static_content', allow_reuse=True)
    def validate_static_content(cls, paths: Localized[Path]):
        for path in paths.values():
            if path.is_absolute():
                raise ValueError("Path must be relative")
        return paths

Parent.update_forward_refs()
Exercise.update_forward_refs()
LTIExercise.update_forward_refs()
ExerciseCollection.update_forward_refs()
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


Float0to1 = confloat(ge=0, le=1)


class Module(Parent):
    name: Localized[str]
    key: str
    status: str
    order: NotRequired[int]
    introduction: NotRequired[str]
    open: NotRequired[datetime]
    close: NotRequired[datetime]
    duration: NotRequired[Union[timedelta, SimpleDuration]]
    read_open: NotRequired[Optional[datetime]] = Field(alias="read-open")
    points_to_pass: NotRequired[NonNegativeInt]
    late_close: NotRequired[datetime]
    late_penalty: NotRequired[Float0to1]
    late_duration: NotRequired[Union[timedelta, SimpleDuration]]
    numerate_ignoring_modules: NotRequired[bool]

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
    archive_time: NotRequired[datetime]
    assistants: NotRequired[List[str]]
    categories: Dict[str, Any] = {} # TODO: add a pydantic model for categories
    contact: NotRequired[str]
    content_numbering: NotRequired[str]
    course_description: NotRequired[str]
    course_footer: NotRequired[str]
    description: NotRequired[str]
    start: NotRequired[datetime]
    end: NotRequired[datetime]
    enrollment_audience: NotRequired[str]
    enrollment_end: NotRequired[datetime]
    enrollment_start: NotRequired[datetime]
    head_urls: List[AnyHttpUrl] = []
    index_mode: NotRequired[str]
    lifesupport_time: NotRequired[datetime]
    module_numbering: NotRequired[str]
    numerate_ignoring_modules: NotRequired[bool]
    view_content_to: NotRequired[str]
    static_dir: NotRequired[str]

    @validator('modules', allow_reuse=True)
    def validate_module_keys(cls, modules: List[Module]) -> List[Module]:
        keys = []
        for m in modules:
            if m.key in keys:
                raise ValueError(f"Duplicate module key: {m.key}")
            keys.append(m.key)
        return modules

    @root_validator(allow_reuse=True, skip_on_failure=True)
    def validate_categories(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        for m in values["modules"]:
            for c in m.child_categories():
                if c not in values["categories"]:
                    raise ValueError(f"Category not found in categories: {c}")
        return values

    @root_validator(allow_reuse=True, skip_on_failure=True)
    def validate_module_dates(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        for m in values["modules"]:
            if m.close and values.get("end") and m.close > values["end"]:
                m.add_warning(f"Course ends before module closes")

            if m.late_close:
                close = m.close or values["end"]
                if close and m.late_close < close:
                    m.add_warning(f"'late_close' is before 'close'")
        return values
