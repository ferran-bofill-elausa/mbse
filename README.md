# MBSE

Python runtime for executing MBSE JSON models.

## Install

From another project, install this repo in editable mode:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e /path/to/mbse
```

For development and tests:

```bash
pip install -e "/path/to/mbse[test]"
pytest
```

## Basic Usage

```python
from mbse.model.project.project_registry import ProjectRegistry
from mbse.runtime.runtime import Runtime

registry = ProjectRegistry.load("project.json")
runtime = Runtime()
runtime.init(registry)
runtime.play()
```
