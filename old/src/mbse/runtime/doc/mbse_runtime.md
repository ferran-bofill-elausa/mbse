# MBSE runtime package

`mbse.runtime` is the container for executable runtime implementations.

## Current runtime families

- `mbse.runtime.hsm` — hierarchical state machine runtime, generator, and preparation pipeline.

## Responsibility boundaries

The package root stays implementation-agnostic. Concrete runtime behavior, builders, generator code, and runtime-specific docs live inside the corresponding subpackage.
