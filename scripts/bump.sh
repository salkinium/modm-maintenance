#!/bin/sh
# Updates the modm-ext/*-partial submodules of the modm checkout in the current
# directory to their latest commit and commits them with their versions.
# Updates that only change the update scripts or CI of the partial repo are skipped.
set -e

# Version from the last "Update ..." commit subject, else the commit date
version() {
  s=$(git -C "$1" log -1 --format=%s --grep='^Update' "$2")
  v=$(echo "$s" | grep -oE '[0-9]+(\.[0-9]+)+' | tail -1)
  case "$s" in *" v$v"*) v="v$v" ;; esac
  echo "${v:-$(git -C "$1" log -1 --format=%cs "$2")}"
}

msg=""
for s in $(git config -f .gitmodules --get-regexp 'submodule\..*\.url' | grep -- '-partial' \
           | sed 's/^submodule\.\(.*\)\.url .*/\1/'); do
  p=$(git config -f .gitmodules "submodule.$s.path")
  old=$(git rev-parse "HEAD:$p")
  git submodule update -q --remote "$p"
  new=$(git -C "$p" rev-parse HEAD)
  if [ -z "$(git -C "$p" diff --name-only "$old" "$new" \
             | grep -vE '^(update\.py|partial\.py|README\.md|\.gitignore|\.github/)')" ]; then
    git submodule update -q "$p"  # back to the pinned commit
    continue
  fi
  git add "$p"
  msg="$msg
- ${p#ext/}: $(version "$p" "$old") → $(version "$p" "$new")"
done

if [ -z "$msg" ]; then echo "No source changes"; exit 0; fi
git commit -q -m "[ext] Update partial submodules" -m "${msg#?}"
git log -1 --format=%B
