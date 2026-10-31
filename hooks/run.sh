#!/bin/sh
# Run hooks/<name>.py with the first working Python 3: python3, python, py -3.
# The hook event on stdin passes through. Kept in a file so Claude Code's
# hook messages show a short command instead of this loop.
name=$1
dir=$(dirname "$0")
for py in python3 python 'py -3'; do
  if $py -c '' >/dev/null 2>&1; then exec $py "$dir/$name.py"; fi
done
echo "[bighead $name] no Python 3 found; hook inactive" >&2
exit 1
