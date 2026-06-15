from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HsmValidationError(Exception):
  code: str
  message: str

  def __str__(self) -> str:
    return self.message


__all__ = ["HsmValidationError"]
