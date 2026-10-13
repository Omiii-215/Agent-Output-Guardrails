"""Import every model module so ``Base.metadata`` is complete (Alembic, tests)."""

from backend.actions import models as action_models  # noqa: F401
from backend.adapters.payments import simulator  # noqa: F401
from backend.ai import explanations  # noqa: F401
from backend.approvals import models as approval_models  # noqa: F401
from backend.audit import exports as audit_exports  # noqa: F401
from backend.cases import models as case_models  # noqa: F401
from backend.evidence import models as evidence_models  # noqa: F401
from backend.identity import models as identity_models  # noqa: F401
from backend.modules.invoices import models as invoice_models  # noqa: F401
from backend.modules.reconciliation import models as reconciliation_models  # noqa: F401
from backend.persistence import idempotency, jobs  # noqa: F401
from backend.persistence.base import Base
from backend.policies import models as policy_models  # noqa: F401
from backend.telemetry import audit  # noqa: F401

metadata = Base.metadata
