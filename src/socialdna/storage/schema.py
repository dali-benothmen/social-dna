"""Current Core table definitions, composed from frozen schema slices."""

from socialdna.storage.migrations.versions.v0001_foundation import foundation_metadata
from socialdna.storage.migrations.versions.v0002_timeline import extend_metadata
from socialdna.storage.migrations.versions.v0003_enrichment import extend_metadata as enrichment

metadata = foundation_metadata()
extend_metadata(metadata)
enrichment(metadata)
