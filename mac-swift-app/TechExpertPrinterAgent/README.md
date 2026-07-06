# TechExpert Printer Agent — App Nativa macOS

Aplicación nativa **SwiftUI** para Intel iMac 2020 (macOS Sonoma 14+).

Fondo blanco, texto azul, controles limpios. Sin Python, sin tkinter, sin dependencias externas.

## 📦 Contenido

- `TechExpertPrinterAgent.xcodeproj/` — Proyecto Xcode listo para abrir
- `TechExpertPrinterAgent/` — Código fuente Swift
  - `agent-macos-x64` — Binario del Printer Agent (compilado para Intel)
  - `icon.png` — Icono de la app

## 🚀 Cómo usarlo (en tu Mac)

### 1. Abrir en Xcode

```bash
open TechExpertPrinterAgent.xcodeproj
```

### 2. Compilar y ejecutar

**Product → Run** (Cmd+R)

Xcode firma automáticamente con tu certificado de desarrollador (Apple ID gratis vale).

### 3. Configurar

1. Obtén el token desde el panel **Administración → Impresora** en SatTPV
2. Pégalo en el campo **Token de conexión**
3. Haz clic en **Conectar**

### 4. Usar

- **🧾 Probar ticket** — Imprime un ticket de prueba
- **💰 Abrir cajón** — Abre el cajón portamonedas
- **🔍 Estado** — Comprueba el estado del agente
- **❌ Desconectar** — Desconecta el agente

## 🔧 Funcionamiento interno

La app lanza `agent-macos-x64` como subproceso y se comunica con él mediante **comandos JSON por stdin**. El agente se conecta al servidor SatTPV vía WebSocket (túnel).

**No necesita puertos locales abiertos.** Todo va cifrado por el túnel.

## 📦 Distribuir a clientes

Hay dos scripts listos en `../macos-packaging/`:

### 🆓 Gratuito — .pkg con postinstall
```bash
cd ../macos-packaging
./build-macos-pkg.sh
```
Genera un `.pkg` que:
- Instala la app en `/Applications/`
- El postinstall elimina cuarentena y firma ad-hoc
- El cliente solo hace doble clic → Instalar

### 💼 Oficial — Developer ID + Notarización ($99/año)
```bash
cd ../macos-packaging
# Edita las variables del script primero
./notarize-macos.sh
```
Genera un `.pkg` **notarizado por Apple**:
- Cero advertencias Gatekeeper
- Cero comandos para el cliente
- Experiencia profesional

## 📋 Requisitos

- macOS Sonoma 14.0+
- Xcode 15.2+
- Apple ID (gratuito) para desarrollo local
