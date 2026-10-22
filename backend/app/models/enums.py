from enum import StrEnum

from sqlalchemy import Enum as SAEnum


class WorkspaceRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"


class ProjectRole(StrEnum):
    MANAGER = "manager"
    DEVELOPER = "developer"
    TESTER = "tester"
    DESIGNER = "designer"


def str_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    """Portable enum column: VARCHAR + CHECK constraint, stores the enum *values*."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda cls: [m.value for m in cls],
        validate_strings=True,
    )
