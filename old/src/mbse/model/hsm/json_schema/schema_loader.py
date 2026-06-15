"""Schema loader for HSM JSON v1."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources


@lru_cache(maxsize=1)
def load_hsm_schema() -> dict[str, object]:
  """Load the authoritative HSM JSON Schema document."""

  schema_path = resources.files("mbse.model.hsm.json_schema").joinpath(
    "hsm_schema_v1.json"
  )
  return json.loads(schema_path.read_text(encoding="utf-8"))

__all__ = ["load_hsm_schema"]
