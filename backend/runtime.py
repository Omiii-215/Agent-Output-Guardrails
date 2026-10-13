"""Process-wide wiring of adapters shared by the API and the worker."""

from __future__ import annotations

from dataclasses import dataclass

from backend.adapters.crypto import FieldCipher
from backend.adapters.models.base import ModelProvider
from backend.adapters.models.fake import FakeModelProvider
from backend.adapters.object_store.grants import GrantSigner
from backend.adapters.object_store.store import LocalObjectStore, ObjectStore
from backend.adapters.payments.simulator import PaymentAdapter, SimulatedPaymentProvider
from backend.config import Settings
from backend.evidence.inspection import Scanner, SignatureScanner
from backend.persistence.database import Database


@dataclass
class Runtime:
    settings: Settings
    db: Database
    objects: ObjectStore
    grants: GrantSigner
    scanner: Scanner
    cipher: FieldCipher
    models: ModelProvider
    payments: PaymentAdapter


def build_runtime(settings: Settings, db: Database | None = None) -> Runtime:
    db = db or Database(settings.database_url, admin_url=settings.database_admin_url)
    return Runtime(
        settings=settings,
        db=db,
        objects=LocalObjectStore(settings.object_store_path),
        grants=GrantSigner(settings.object_grant_secret, settings.object_grant_ttl_seconds),
        scanner=SignatureScanner(),
        cipher=FieldCipher(settings.field_encryption_key),
        models=build_model_provider(settings),
        # Live connectors stay disabled until their release gate (ADR 0006).
        payments=SimulatedPaymentProvider(db, settings.simulator_webhook_secret),
    )


def build_model_provider(settings: Settings) -> ModelProvider:
    if settings.model_provider == "bedrock":
        from backend.adapters.models.bedrock import BedrockModelProvider

        if not settings.bedrock_model_id:
            raise ValueError("FINGUARD_BEDROCK_MODEL_ID is required for the Bedrock provider")
        return BedrockModelProvider(
            settings.bedrock_model_id,
            region=settings.bedrock_region,
            guardrail_id=settings.bedrock_guardrail_id,
            guardrail_version=settings.bedrock_guardrail_version,
            timeout_seconds=settings.model_timeout_seconds,
        )
    return FakeModelProvider()
