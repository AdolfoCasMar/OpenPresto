#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ "${1:-}" != "" && "${1:-}" != --install ]]; then
  echo "Uso: bash scripts/construir-flatpak.sh [--install]" >&2
  exit 2
fi
for tool in flatpak flatpak-builder; do
  command -v "$tool" >/dev/null || { echo "Falta $tool. Ejecuta bash scripts/instalar-kubuntu.sh." >&2; exit 1; }
done
APP_ID=org.openpresto.OpenPresto
BRANCH=6.10
flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user -y flathub "org.kde.Platform//$BRANCH" "org.kde.Sdk//$BRANCH" "io.qt.PySide.BaseApp//$BRANCH"
options=(--user --force-clean --repo="$ROOT/repo-flatpak")
if [[ "${1:-}" == --install ]]; then options+=(--install); fi
flatpak-builder "${options[@]}" "$ROOT/build-flatpak" "$ROOT/$APP_ID.json"
mkdir -p "$ROOT/dist"
ARCH="$(flatpak --default-arch)"
OPENPRESTO_VERSION="$(sed -n 's/^__version__ = "\([^"]*\)"[[:space:]]*$/\1/p' openpresto/__init__.py)"
if [[ ! "$OPENPRESTO_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+[a-zA-Z0-9.-]*$ ]]; then
  echo "No se pudo leer una versión válida de OpenPresto." >&2
  exit 1
fi
BUNDLE="$ROOT/dist/OpenPresto-$OPENPRESTO_VERSION-$ARCH.flatpak"
flatpak build-bundle --runtime-repo=https://flathub.org/repo/flathub.flatpakrepo "$ROOT/repo-flatpak" "$BUNDLE" "$APP_ID"
sha256sum "$BUNDLE" > "$BUNDLE.sha256"
echo "Paquete generado: $BUNDLE"
echo "Instalación en otro equipo con Flatpak: flatpak install --user \"$BUNDLE\""
