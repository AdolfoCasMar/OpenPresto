#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p dist
exec > >(tee "$ROOT/dist/instalacion-kubuntu.log") 2>&1
trap 'echo "La preparación no terminó. Comparte dist/instalacion-kubuntu.log para revisar el error." >&2' ERR

if [[ "$(uname -s)" != Linux ]]; then
  echo "Ejecuta este archivo en el equipo con Kubuntu." >&2
  exit 1
fi
if [[ "$EUID" == 0 ]]; then
  echo "Ejecuta el script como usuario normal, sin sudo. Se pedirá sudo solo para instalar herramientas." >&2
  exit 1
fi
echo "OpenPresto · preparación local para Kubuntu/Debian KDE"
echo "Se instalarán Flatpak y sus herramientas si faltan, y las bases KDE/PySide en tu usuario."
echo "La primera descarga puede ocupar varios GB. Se necesita conexión durante esta preparación."
if ! command -v flatpak >/dev/null || ! command -v flatpak-builder >/dev/null || ! dpkg-query -W -f='${Status}' xdg-desktop-portal-kde 2>/dev/null | grep -q 'install ok installed'; then
  sudo apt-get update
  sudo apt-get install -y flatpak flatpak-builder xdg-desktop-portal xdg-desktop-portal-kde
fi
flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
bash "$ROOT/scripts/construir-flatpak.sh" --install
echo
echo "Instalación completada. Abre OpenPresto desde el menú o ejecuta:"
echo "flatpak run org.openpresto.OpenPresto"
echo "Si acabas de instalar Flatpak y el icono no aparece, cierra y vuelve a iniciar la sesión."
