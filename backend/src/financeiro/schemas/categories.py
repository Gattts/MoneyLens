from typing import Annotated

from pydantic import StringConstraints

from financeiro.domain.enums import Bucket, Kind
from financeiro.schemas.common import Flag, Icon, InputModel, Name, OutputModel


class CategoryIn(InputModel):
    name: Name
    icon: Icon = ""
    description: Annotated[str, StringConstraints(max_length=300)] = ""
    kind: Kind
    default_bucket: Bucket | None = None
    archived: Flag = False


class CategoryOut(OutputModel):
    id: int
    name: str
    icon: str
    description: str
    kind: Kind
    default_bucket: Bucket | None
    archived: bool
