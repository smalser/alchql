import pkg_resources

from .fields import SQLAlchemyConnectionField
from .types import SQLAlchemyObjectType
from .utils import get_query
from .sql_mutation import SQLAlchemyUpdateMutation

__version__ = "3.0.6"

__all__ = [
    "__version__",
    "SQLAlchemyObjectType",
    "SQLAlchemyConnectionField",
    "SQLAlchemyUpdateMutation",
    "get_query",
]


if pkg_resources.get_distribution("SQLAlchemy").parsed_version.release < (1, 4):
    raise Exception("Use SQLAlchemy version > 1.4")
