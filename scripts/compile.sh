#!/bin/sh
# Quick-compile modm (the current directory) for the given test/all targets
# inside the same container image modm's CI uses.
# Usage: compile.sh stm32f4 stm32g0 ...    (AVR targets "at..." use the avr image)
set -e
case "$1" in
  at*) image="$IMAGE_AVR" ;;
  *)   image="$IMAGE_CORTEX" ;;
esac
exec docker run --rm -v "$PWD:/w" -w /w/test/all "$image" sh -c \
  "git config --global --add safe.directory '*' &&
   pip3 install -q --upgrade --break-system-packages modm &&
   python3 run_all.py $* --quick"
