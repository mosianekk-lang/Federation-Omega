#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/mosianekk-lang/Federation-Omega.git"
WORKDIR="${HOME}/Federation-Omega"

if [ -d "${WORKDIR}/.git" ]; then
  git -C "${WORKDIR}" fetch --all --prune
  git -C "${WORKDIR}" reset --hard origin/main
else
  rm -rf "${WORKDIR}"
  git clone "${REPO_URL}" "${WORKDIR}"
fi

cd "${WORKDIR}"
bash ops/activate_wif_and_deploy.sh
