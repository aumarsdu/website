#!/usr/bin/env bash

set -Eeuo pipefail

APP_ROOT="${1:-/var/www/helipei-official}"
PACKAGE_PATH="${2:-/tmp/helipei-official.tgz}"
RELEASES_DIR="${APP_ROOT}/releases"
CURRENT_LINK="${APP_ROOT}/current"
TIMESTAMP="$(date +%Y%m%d%H%M%S)"
NEW_RELEASE_DIR="${RELEASES_DIR}/${TIMESTAMP}"

if [ ! -f "${PACKAGE_PATH}" ]; then
  echo "部署包不存在: ${PACKAGE_PATH}" >&2
  exit 1
fi

mkdir -p "${RELEASES_DIR}"
mkdir -p "${NEW_RELEASE_DIR}"

tar -xzf "${PACKAGE_PATH}" -C "${NEW_RELEASE_DIR}"
ln -sfn "${NEW_RELEASE_DIR}" "${CURRENT_LINK}"

find "${RELEASES_DIR}" -mindepth 1 -maxdepth 1 -type d | sort | head -n -5 | xargs -r rm -rf
rm -f "${PACKAGE_PATH}" /tmp/helipei-release.sh

reload_nginx() {
  if command -v nginx >/dev/null 2>&1; then
    nginx -t
    if command -v systemctl >/dev/null 2>&1; then
      systemctl reload nginx
    fi
    return 0
  fi

  return 1
}

reload_nginx_with_sudo() {
  if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    sudo -n nginx -t
    if sudo -n command -v systemctl >/dev/null 2>&1; then
      sudo -n systemctl reload nginx
    fi
    return 0
  fi

  return 1
}

if [ "$(id -u)" -eq 0 ]; then
  reload_nginx || true
else
  reload_nginx_with_sudo || true
fi

echo "发布完成: ${CURRENT_LINK} -> ${NEW_RELEASE_DIR}"
