#!/usr/bin/env bash
set -euo pipefail
python -m safeblock.fetch && python -m safeblock.network && python -m safeblock.analyze && python -m safeblock.build_map
