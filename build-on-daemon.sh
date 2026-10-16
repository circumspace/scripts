#!/usr/bin/env bash
set -euo pipefail

# Build a single PKGBUILD on daemon via SSH in a podman container
# Usage: ./build-on-daemon.sh <pkgdir> [image]
#   pkgdir  — directory containing the PKGBUILD (e.g. pkgbuilds/proton-drive-fs)
#   image   — podman image to use (default: archlinux)

PKGDIR="${1:?Usage: $0 <pkgdir> [image]}"
IMAGE="${2:-archlinux}"
REMOTE_DIR="/tmp/pkbuilds-build"

cd "$PKGDIR"
PKGNAME="$(grep '^pkgname=' PKGBUILD | cut -d= -f2)"

echo "==> Uploading ${PKGNAME} source to daemon..."
rsync -avz --delete \
  --exclude='.git' \
  --exclude='*.tar.zst' \
  --exclude='*.pkg.tar.zst' \
  --exclude='*.pkg.tar' \
  --exclude='.SRCINFO' \
  --exclude='pkg/' \
  --exclude='src/' \
  --exclude='.agents' \
  "${PKGDIR}/" \
  "daemon:${REMOTE_DIR}/${PKGNAME}/"

echo "==> Pulling ${IMAGE} image..."
ssh daemon "podman pull ${IMAGE} 2>&1" | tail -3

echo "==> Building ${PKGNAME} in podman container..."
ssh daemon bash -s - "${PKGNAME}" "${REMOTE_DIR}" "${IMAGE}" <<'ENDSSH'
set -euo pipefail
PKGNAME="$1"
BUILD_DIR="$2"
IMAGE="$3"

podman run --rm \
  -v "${BUILD_DIR}/${PKGNAME}:/work:z" \
  -w /work \
  --userns=host \
  --cap-add=ALL \
  "${IMAGE}" \
  bash -c '
    pacman -Syu --noconfirm 2>&1 | tail -5
    pacman -S --noconfirm --needed base-devel go git fuse3 libsecret gtk3 zenity --overwrite="*" 2>&1 | tail -5
    makepkg -si --noconfirm --skippgpcheck 2>&1
  '
ENDSSH

echo "==> Copying built package(s) back..."
rsync -avz "daemon:${REMOTE_DIR}/${PKGNAME}/*.pkg.tar.zst" "${PKGDIR}/"

echo "==> Done. Packages:"
ls -lh "${PKGDIR}"/*.pkg.tar.zst 2>/dev/null || echo "No .pkg.tar.zst found"

# Clean up on daemon
ssh daemon "rm -rf ${REMOTE_DIR}/${PKGNAME}"
