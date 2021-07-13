from typing import Any, Dict, Optional, List, Union
from datetime import datetime, timedelta

from pydantic import BaseModel as PydanticModel, Field

from util.localize import Localized, DEFAULT_LANG


class Parent(PydanticModel):
    children: List[Union["Chapter", "Exercise"]] = []

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
    max_submissions: NonNegativeInt = 0
    allow_assistant_viewing: Optional[bool]
    allow_assistant_grading: Optional[bool]
    config: Optional[Path]
    type: Optional[str]
    confirm_the_level: Optional[bool]
    difficulty: Optional[str]
    min_group_size: Optional[NonNegativeInt]
    max_group_size: Optional[NonNegativeInt]
    max_points: Optional[NonNegativeInt]
    points_to_pass: Optional[NonNegativeInt]

    class Config:
        extra = "forbid"

    @root_validator(allow_reuse=True, skip_on_failure=True)
    def validate_assistant_permissions(cls, values: Dict[str, Any]):
        if not values.get("allow_assistant_viewing", False) and values.get("allow_assistant_grading", True):
            raise ValueError("Assistant grading is allowed but viewing is not")
        return values


class Chapter(Item):
    static_content: Localized[Path]
    generate_table_of_contents: Optional[bool]

    class Config:
        extra = "forbid"

    @validator('static_content', allow_reuse=True)
    def validate_static_content(cls, paths: Localized[Path]):
        for path in paths.values():
            if path.is_absolute():
                raise ValueError("Path must be relative")
        return paths

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


Float0to1 = confloat(ge=0, le=1)


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
    points_to_pass: Optional[NonNegativeInt]
    late_close: Optional[datetime]
    late_penalty: Optional[Float0to1]
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
    head_urls: List[AnyHttpUrl] = []
    index_mode: Optional[str]
    lifesupport_time: Optional[datetime]
    module_numbering: Optional[str]
    numerate_ignoring_modules: Optional[bool]
    view_content_to: Optional[str]
    static_dir: Optional[str]

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
                raise ValueError("Module close must be before course end")

            if m.late_close:
                close = m.close or values["end"]
                if close and m.late_close < close:
                    raise ValueError("Module late_close must be after close")
        return values
