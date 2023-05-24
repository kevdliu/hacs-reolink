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

# Configuration
if [[ $* == *"--force-update"* ]]; then
    force_update=true
else
    force_update=false
fi

# Colors
if [[ $* != *"--no-color"* ]]; then
    RED="\033[31m"
    GREEN="\033[32m"
    CYAN="\033[36m"
    NORMAL="\033[0;39m"
fi

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
    if [ "$force_update" = true ]; then
        ok "HACS is up to date but force update is enabled. Continuing."
    else
        ok "HACS is up to date"
        exit 0
    fi
fi

divider 

echo "$rebase"
ok "Rebased to latest release tag ${tag}"

divider

git push -f "$HASS_REMOTE_FORK" "$HASS_BRANCH_NAME"
ok "Pushed latest changes to remote (${HASS_REMOTE_FORK})"

divider

cd - > /dev/null

git pull -X theirs origin "$HACS_BRANCH_NAME"

rm -rf "./${HACS_COMPONENT_PATH}/${COMPONENT_NAME}"
cp -rf "../${HASS_REPO_DIR}/${HASS_COMPONENT_PATH}/${COMPONENT_NAME}" "./${HACS_COMPONENT_PATH}"
ok "Copied latest changes to HACS repo"

divider

mkdir "${HACS_COMPONENT_PATH}/${COMPONENT_NAME}/translations"
cp -f "${HACS_COMPONENT_PATH}/${COMPONENT_NAME}/strings.json" "${HACS_COMPONENT_PATH}/${COMPONENT_NAME}/translations/en.json"
ok "Copied translations file"

divider

status=$(git status --porcelain)
if [ -n "$status" ]; then
    echo "$status"
    changes=$(echo "$status" | wc -l)
    ok "${changes} files have changed in ${COMPONENT_NAME}"

    divider

    echo "# Reolink" > info.md
    echo "Latest version is based on Home Assistant ${tag}" >> info.md

    git add -A
    git commit -m "Rebase to ${tag}"
    ok "Committed changes to local repository"
else
    if [ "$force_update" = true ]; then
        ok "No changes detected for ${COMPONENT_NAME} but force update is enabled. Continuing."
    else
        ok "No changes detected for ${COMPONENT_NAME}"
        exit 0
    fi
fi

divider

git push origin "$HACS_BRANCH_NAME"
ok "Pushed changes to HACS (${HACS_BRANCH_NAME})"

divider

hash=$(git rev-parse --short HEAD)
ok "Successfully rebased ${COMPONENT_NAME} to ${tag}. New commit hash is ${hash}."

exit 0
