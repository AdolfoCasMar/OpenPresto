#!/usr/bin/env bash
set -u
echo "=== OpenPresto: diagnóstico técnico sin documentos de usuario ==="
date -Iseconds
if [[ -f /etc/os-release ]]; then cat /etc/os-release; fi
uname -m
echo "Sesión gráfica: ${XDG_SESSION_TYPE:-desconocida}"
flatpak --version 2>&1
flatpak info --user org.openpresto.OpenPresto 2>&1
flatpak list --user --runtime --columns=application,branch,version 2>&1
flatpak run --command=python3 org.openpresto.OpenPresto -c 'import sys; from PySide6.QtCore import qVersion; import PySide6; print(sys.version); print("PySide", PySide6.__version__, "Qt", qVersion())' 2>&1
