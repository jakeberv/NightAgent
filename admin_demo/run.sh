#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python="$here/../.venv/bin/python"
if [ ! -x "$python" ]; then python=python3; fi
exec "$python" "$here/run.py" "$@"
