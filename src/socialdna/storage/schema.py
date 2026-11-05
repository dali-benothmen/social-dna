"""Current Core table definitions, composed from frozen schema slices."""

from socialdna.storage.migrations.versions.v0001_foundation import foundation_metadata
from socialdna.storage.migrations.versions.v0002_timeline import extend_metadata
from socialdna.storage.migrations.versions.v0003_enrichment import extend_metadata as enrichment
from socialdna.storage.migrations.versions.v0004_analytics import extend_metadata as analytics
from socialdna.storage.migrations.versions.v0005_evidence import extend_metadata as evidence
from socialdna.storage.migrations.versions.v0006_designs import extend_metadata as designs
from socialdna.storage.migrations.versions.v0007_creative import extend_metadata as creative
from socialdna.storage.migrations.versions.v0008_audience import extend_metadata as audience
from socialdna.storage.migrations.versions.v0009_behavioral import extend_metadata as behavioral
from socialdna.storage.migrations.versions.v0010_memory import extend_metadata as memory
from socialdna.storage.migrations.versions.v0011_research import extend_metadata as research
from socialdna.storage.migrations.versions.v0012_reevaluation import extend_metadata as reevaluation
from socialdna.storage.migrations.versions.v0013_context import extend_metadata as context

metadata = foundation_metadata()
extend_metadata(metadata)
enrichment(metadata)
analytics(metadata)
evidence(metadata)
designs(metadata)
creative(metadata)
audience(metadata)
behavioral(metadata)
memory(metadata)
research(metadata)
reevaluation(metadata)
context(metadata)
