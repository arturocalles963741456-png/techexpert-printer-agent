# TechExpert Printer Agent — Empaquetado macOS

## Dos opciones de distribución

### 🆓 Opción gratuita — .pkg con postinstall

Script: `build-macos-pkg.sh`

**Cómo usarlo:**
1. Abre Terminal en tu Mac
2. `cd macos-packaging/`
3. `./build-macos-pkg.sh`

**Resultado:** `output/TechExpert Printer Agent-Installer.pkg`

**Qué hace el script:**
- Compila la app con `xcodebuild`
- La firma ad-hoc (`codesign -s -`)
- Crea un .pkg que instala en `/Applications/`
- El postinstall elimina cuarentena y vuelve a firmar al instalarse

**Experiencia del cliente:**
- Descarga el .pkg
- Doble clic → Instalador → App en Aplicaciones
- Solo la **primera vez**: botón derecho > "Abrir" (por la firma ad-hoc)

### 💼 Opción oficial — Developer ID + Notarización

Script: `notarize-macos.sh`

**Requisitos:**
- Apple Developer Program ($99/año)
- Certificados Developer ID en tu llavero

**Configuración única (una vez):**
```bash
xcrun notarytool store-credentials "AC_PASSWORD" \
  --apple-id "tu@email.com" \
  --team-id "TU_TEAM_ID" \
  --password "app-specific-password"
```

**Cómo usarlo:**
1. Abre Terminal en tu Mac
2. `cd macos-packaging/`
3. Edita las variables al inicio del script (Developer ID name, Apple ID)
4. `./notarize-macos.sh`

**Resultado:** `output/TechExpert-Printer-Agent-2.0.0.pkg` (notarizado)

**Experiencia del cliente:**
- Descarga el .pkg
- Doble clic → Instala sin ningún aviso
- **Cero advertencias Gatekeeper. Cero comandos.**
- Experiencia profesional completa

## Estructura

```
macos-packaging/
├── build-macos-pkg.sh     # Opción gratuita (ad-hoc + pkg)
├── notarize-macos.sh       # Opción oficial (Developer ID + notarizar)
├── scripts/
│   └── postinstall         # Script que se ejecuta al instalar el .pkg
└── output/                 # Aquí se generan los .pkg
```

## Notas

- Los scripts se ejecutan en **macOS**, no en Linux
- El postinstall se ejecuta como root durante la instalación del .pkg
- El primer build desde Xcode puede descargar dependencias (SwiftUI)
