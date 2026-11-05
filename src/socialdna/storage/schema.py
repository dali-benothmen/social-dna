"""Current Core table definitions, composed from frozen schema slices."""

from socialdna.storage.migrations.versions.v0001_foundation import foundation_metadata
from socialdna.storage.migrations.versions.v0002_timeline import extend_metadata
from socialdna.storage.migrations.versions.v0003_enrichment import extend_metadata as enrichment
from socialdna.storage.migrations.versions.v0004_analytics import extend_metadata as analytics
from socialdna.storage.migrations.versions.v0005_evidence import extend_metadata as evidence
from socialdna.storage.migrations.versions.v0006_designs import extend_metadata as designs
from socialdna.storage.migrations.versions.v0007_creative import extend_metadata as creative
from socialdna.storage.migrations.versions.v0008_audience import extend_metadata as audience

metadata = foundation_metadata()
extend_metadata(metadata)
enrichment(metadata)
analytics(metadata)
evidence(metadata)
designs(metadata)
creative(metadata)
audience(metadata)
