"""Import every model module so ``Base.metadata`` is complete (Alembic, tests)."""

from backend.cases import models as case_models  # noqa: F401
from backend.evidence import models as evidence_models  # noqa: F401
from backend.identity import models as identity_models  # noqa: F401
from backend.persistence.base import Base
from backend.telemetry import audit  # noqa: F401

metadata = Base.metadata
