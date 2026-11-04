"""Current Core table definitions, composed from frozen schema slices."""

from socialdna.storage.migrations.versions.v0001_foundation import foundation_metadata
from socialdna.storage.migrations.versions.v0002_timeline import extend_metadata

metadata = foundation_metadata()
extend_metadata(metadata)
