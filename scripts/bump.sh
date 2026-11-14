#!/bin/sh
# Updates the modm-ext/* and modm-io/* submodules of the modm checkout in the current
# directory to their latest commit and commits them with their versions.
# Moved repositories get their new URL in .gitmodules.
# Updates that only change the update machinery or file modes are skipped.
# modm-devices is skipped, it is updated together with modm's device code.
set -e

# Version from the last "Update ..." commit subject, else the commit date
version() {
  s=$(git -C "$1" log -1 --format=%s --grep='^Update' "$2")
  v=$(echo "$s" | grep -oE '[0-9]+(\.[0-9]+)+' | tail -1)
  case "$s" in *" v$v"*) v="v$v" ;; esac
  echo "${v:-$(git -C "$1" log -1 --format=%cs "$2")}"
}

msg=""
for s in $(git config -f .gitmodules --get-regexp 'submodule\..*\.url' \
           | grep -E 'github\.com/modm-(ext|io)/' | grep -vE '/(modm-devices|ros-lib)' \
           | sed 's/^submodule\.\(.*\)\.url .*/\1/'); do
  p=$(git config -f .gitmodules "submodule.$s.path")
  url=$(git config -f .gitmodules "submodule.$s.url")
  repo=$(echo "$url" | sed 's#.*github\.com/##; s#\.git$##')
  moved=$(gh api "repos/$repo" -q .full_name)
  if [ -n "$moved" ] && [ "$moved" != "$repo" ]; then
    git config -f .gitmodules "submodule.$s.url" "https://github.com/$moved.git"
    git submodule sync -q "$p"
    git add .gitmodules
    msg="$msg
- ${p#ext/}: moved to $moved"
  fi
  old=$(git rev-parse "HEAD:$p")
  git submodule update -q --remote "$p"
  new=$(git -C "$p" rev-parse HEAD)
  # numstat "0 0" = file mode change only. Keep in sync with check_partials.py!
  if [ -z "$(git -C "$p" diff --numstat "$old" "$new" | grep -vE '^0	0	' | cut -f3 \
             | grep -vE '^(update\.py|partial\.py|README\.md|\.gitignore|\.github/|tests?/|docs/|tools/)')" ]; then
    git submodule update -q "$p"  # back to the pinned commit
    continue
  fi
  git add "$p"
  msg="$msg
- ${p#ext/}: $(version "$p" "$old") → $(version "$p" "$new")"
done

if [ -z "$msg" ]; then echo "No source changes"; exit 0; fi
git commit -q -m "[ext] Update submodules" -m "${msg#?}"
git log -1 --format=%B
