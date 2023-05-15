#!/bin/sh

set -e

# Configuration
COMPONENT_NAME="reolink"

HASS_REPO_DIR="hass"
HASS_COMPONENT_PATH="homeassistant/components/"
HASS_BRANCH_NAME="hacs/reolink"
HASS_REMOTE_FORK="fork"

HACS_BRANCH_NAME="master"
HACS_COMPONENT_PATH="custom_components/"

# Colors
RED="\033[31m"
GREEN="\033[32m"
CYAN="\033[36m"
NORMAL="\033[0;39m"

# Utility

ok () {
    echo -e "${CYAN}----------------------------------"
    echo -e "${GREEN}$1"
    echo -e "${CYAN}----------------------------------${NORMAL}"
}

error () {
    echo -e "${CYAN}----------------------------------"
    echo -e "${RED}$1"
    echo -e "${CYAN}----------------------------------${NORMAL}"
    exit 1
}

divider () {
    echo -e "\n\n"
}

# Start

cd "../${HASS_REPO_DIR}"

current=$(git branch --show-current)
if [[ "$current" != "$HASS_BRANCH_NAME" ]]; then
    error "Current working branch (${current}) is not HACS branch (${HASS_BRANCH_NAME})"
fi

rm -rf ".git/rebase-apply"

git fetch --all --prune

tag=$(git describe --tags $(git rev-list --tags --max-count=1))

ok "Latest Home Assistant release tag is ${tag}"

rebase=$(git rebase "$tag" "$HASS_BRANCH_NAME")

if [[ "$rebase" == *"up to date"* ]]; then
  ok "HACS is up to date"
  exit 0
fi

divider 

echo "$rebase"
ok "Rebased to latest release tag ${tag}"

divider

git push -f "$HASS_REMOTE_FORK" "$HASS_BRANCH_NAME"
ok "Pushed latest changes to remote (${HASS_REMOTE_FORK})"

cd - > /dev/null
rm -rf "./${HACS_COMPONENT_PATH}/${COMPONENT_NAME}"
cp -rf "../${HASS_REPO_DIR}/${HASS_COMPONENT_PATH}/${COMPONENT_NAME}" "./${HACS_COMPONENT_PATH}"
ok "Copied latest changes to HACS repo"

status=$(git status --porcelain)
if [ -z "$status" ]; then
    ok "No changes detected for ${COMPONENT_NAME}"
    exit 0
fi

divider

echo "$status"
changes=$(echo "$status" | wc -l)
ok "${changes} files have changed in ${COMPONENT_NAME}"

git add -A
git commit -m "Rebased to ${tag}"
ok "Committed changes to local repository"

divider

git push origin "$HACS_BRANCH_NAME"
ok "Pushed changes to HACS (${HACS_BRANCH_NAME})"

divider

hash=$(git rev-parse --short HEAD)
ok "Successfully rebased ${COMPONENT_NAME} to ${tag}. New commit hash is ${hash}."

exit 0
