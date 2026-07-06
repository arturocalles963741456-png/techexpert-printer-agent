# 🖨️ TechExpert TPV — Printer Agent

Agente local para imprimir tickets y abrir cajón de dinero desde el navegador.

## Requisitos

- **Node.js** 18+
- Una **impresora térmica** conectada por:
  - **Red (IP)** → Puerto 9100 (recomendado)
  - **USB** → Drivers instalados en el sistema

## Instalación

```bash
cd printer-agent
npm install
```

## Configuración

Edita `config.json` (se crea automáticamente al ejecutar):

```json
{
  "printer_host": "192.168.1.100",
  "printer_port": 9100,
  "agent_port": 19100,
  "printer_type": "network"
}
```

- `printer_host`: IP de la impresora térmica (solo para tipo `network`)
- `printer_port`: Puerto TCP (normalmente 9100)
- `agent_port`: Puerto donde escucha este agente (no tocar)
- `printer_type`: `network` o `usb`

## Uso

```bash
node agent.js
```

Se queda ejecutándose en segundo plano. El TPV se conecta automáticamente.

## Conexiones soportadas

| Tipo | Descripción | Cash Drawer |
|------|-------------|-------------|
| network | Impresora por IP (puerto 9100) | ✅ ESC/POS |
| usb | Impresora USB con driver genérico | ✅ ESC/POS |
| browser | Fallback: `window.print()` | ❌ Manual |

## Comandos ESC/POS

Enviados automáticamente:
- **Abrir cajón:** `ESC p 0 50 250`
- **Corte parcial:** `GS V 1`
- **Negrita:** `ESC E 1` / `ESC E 0`
- **Alineación centro:** `ESC a 1`
