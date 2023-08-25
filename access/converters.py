from .config import ConfigSource


class BasenameConverter:
    regex="[\w\d\_\-\.]*"

    def to_python(self, value: str) -> str:
        return value

    def to_url(self, value: str) -> str:
        return value


class ConfigSourceConverter:
    regex="|".join(s.name for s in ConfigSource)

    def to_python(self, value: str) -> ConfigSource:
        return ConfigSource[value]

    def to_url(self, value: ConfigSource) -> str:
        return value.name