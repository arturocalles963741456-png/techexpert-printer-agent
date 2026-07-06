#!/usr/bin/env node
// pkg assets and exclusions
// @pkg assets config.json
// @pkg assets README.md

/**
 * TechExpert TPV — Printer Agent (Tunnel)
 *
 * Se conecta al servidor vía WebSocket (túnel) en lugar de escuchar en puerto local.
 * Soporta reconexión automática con backoff exponencial.
 *
 * Modo fallback local (opcional): si se usa --local, arranca el servidor HTTP antiguo en :19100.
 */

const fs = require('fs');
const path = require('path');
const net = require('net');
const http = require('http');
const WebSocket = require('ws');

// ── ESC/POS library (native USB may fail with pkg) ──
let escpos = null;
let Printer = null;
let USB = null;
let Network = null;
try {
  escpos = require('escpos');
  try { escpos.USB = require('escpos-usb'); } catch(e) { /* USB native not available */ }
  Printer = escpos.Printer;
  USB = escpos.USB;
  Network = escpos.Network;
} catch (e) {
  // noop — fallback to network mode
}

const VERSION = '2.0.0';
const CONFIG_PATH = path.join(__dirname, 'config.json');
const DEFAULT_CONFIG = {
  tunnel_url: 'wss://sattpv.techexpert.cloud/tunnel/agent',
  printer_host: '127.0.0.1',
  printer_port: 9100,
  agent_port: 19100,
  printer_type: 'auto',
  token: null
};

// ── Config ──
function loadConfig() {
  try {
    if (fs.existsSync(CONFIG_PATH)) {
      const data = fs.readFileSync(CONFIG_PATH, 'utf8');
      return { ...DEFAULT_CONFIG, ...JSON.parse(data) };
    }
  } catch (e) {}
  try {
    fs.writeFileSync(CONFIG_PATH, JSON.stringify(DEFAULT_CONFIG, null, 2));
    console.log(`Config created: ${CONFIG_PATH} — add your token and restart`);
  } catch (e) {}
  return DEFAULT_CONFIG;
}

function saveConfig(cfg) {
  try {
    fs.writeFileSync(CONFIG_PATH, JSON.stringify(cfg, null, 2));
  } catch (e) {
    console.error('Failed to save config:', e.message);
  }
}

// ── ESC/POS commands ──
function buildESCPOS(text) {
  const buf = [];
  const w = (b) => buf.push(b);
  w(0x1B); w(0x40);           // Init printer
  w(0x1B); w(0x61); w(0x01);  // Center
  for (let c of 'TIENDA\n') w(c.charCodeAt(0));
  w(0x1B); w(0x61); w(0x00);  // Left
  const now = new Date();
  const ds = now.toLocaleDateString('es-ES') + ' ' + now.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
  for (let c of ds + '\n') w(c.charCodeAt(0));
  for (let i = 0; i < 32; i++) w(0x2D);
  w(0x0A);
  for (let c of text) w(c.charCodeAt(0));
  for (let i = 0; i < 32; i++) w(0x2D);
  w(0x0A);
  w(0x1B); w(0x61); w(0x01);
  for (let c of 'Gracias por su compra\n') w(c.charCodeAt(0));
  w(0x1D); w(0x56); w(0x01);  // Partial cut
  return Buffer.from(buf);
}

function buildDrawerCmd() {
  return Buffer.from([0x1B, 0x70, 0x00, 0x32, 0xFA]);
}

// ── Printer send ──
function sendUSB(data) {
  return new Promise((resolve, reject) => {
    if (!USB) return reject(new Error('USB not available'));
    const device = USB.findPrinter();
    if (!device) return reject(new Error('USB printer not found'));
    device.open((err) => {
      if (err) return reject(err);
      const printer = new Printer(device);
      printer.raw(data);
      printer.close();
      resolve(true);
    });
  });
}

function sendNetwork(data) {
  return new Promise((resolve, reject) => {
    const cfg = loadConfig();
    const sock = new net.Socket();
    sock.setTimeout(5000);
    sock.connect(cfg.printer_port, cfg.printer_host, () => {
      sock.write(data, () => { sock.end(); resolve(true); });
    });
    sock.on('error', reject);
    sock.on('timeout', () => { sock.destroy(); reject(new Error('Timeout')); });
  });
}

function sendToPrinter(data) {
  const cfg = loadConfig();
  if (cfg.printer_type === 'usb' || (cfg.printer_type === 'auto' && USB)) {
    return sendUSB(data).catch(() => sendNetwork(data));
  }
  return sendNetwork(data);
}

// ── WebSocket tunnel connection ──
let ws = null;
let reconnectTimer = null;
let reconnectAttempt = 0;
let heartbeatInterval = null;
let isShuttingDown = false;

// ── Stdin command reader (for macOS app control) ──
const readline = require('readline');
if (process.stdin.isTTY) {
  // Interactive terminal, no stdin commands
} else {
  const rl = readline.createInterface({ input: process.stdin });
  rl.on('line', (line) => {
    try {
      const cmd = JSON.parse(line.trim());
      switch (cmd.command) {
        case 'print_ticket':
          console.log('📨 STDIN: print ticket');
          sendToPrinter(buildESCPOS(cmd.text || 'TEST\nTechExpert TPV\n'))
            .then(() => { console.log(JSON.stringify({ type: 'stdin_result', ok: true, command: 'print_ticket' })); })
            .catch((err) => { console.log(JSON.stringify({ type: 'stdin_result', ok: false, command: 'print_ticket', error: err.message })); });
          break;
        case 'open_drawer':
          console.log('📨 STDIN: open drawer');
          sendToPrinter(buildDrawerCmd())
            .then(() => { console.log(JSON.stringify({ type: 'stdin_result', ok: true, command: 'open_drawer' })); })
            .catch((err) => { console.log(JSON.stringify({ type: 'stdin_result', ok: false, command: 'open_drawer', error: err.message })); });
          break;
        case 'status':
          console.log(JSON.stringify({ type: 'stdin_result', ok: true, command: 'status', connected: !!ws && ws.readyState === WebSocket.OPEN }));
          break;
      }
    } catch(e) {
      console.log(JSON.stringify({ type: 'stdin_result', ok: false, error: e.message }));
    }
  });
}

function connectTunnel() {
  if (isShuttingDown) return;
  const cfg = loadConfig();
  if (!cfg.token) {
    console.log('⚠️  No token configured. Set token in config.json or use the admin panel.');
    console.log('   Retrying in 30s...');
    reconnectTimer = setTimeout(connectTunnel, 30000);
    return;
  }

  const url = cfg.tunnel_url;

  console.log(`\n🔌 Connecting to ${url}...`);
  ws = new WebSocket(url);

  ws.on('open', () => {
    console.log('✅ Connected to tunnel');
    reconnectAttempt = 0;

    // Send auth
    ws.send(JSON.stringify({ type: 'auth', token: cfg.token }));

    // Start heartbeat (every 10s)
    heartbeatInterval = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'heartbeat' }));
      }
    }, 10000);
  });

  ws.on('message', (data) => {
    try {
      const msg = JSON.parse(data.toString());

      switch (msg.type) {
        case 'auth_ok':
          console.log(`🔐 Authenticated! Agent ID: ${msg.agentId}`);
          // Send printer info
          const pinfo = getPrinterInfo();
          ws.send(JSON.stringify({
            type: 'printer_info',
            printer: pinfo.printer,
            printer_type: pinfo.type,
            usb_detected: pinfo.usbDetected,
            version: VERSION
          }));
          break;

        case 'heartbeat_ack':
          // server acknowledged our heartbeat
          break;

        case 'print_ticket':
          console.log('🖨️  Print ticket command received');
          sendToPrinter(buildESCPOS(msg.text || ''))
            .then(() => {
              console.log('✅ Ticket printed');
              if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'print_result', success: true }));
              }
            })
            .catch((err) => {
              console.error('❌ Print failed:', err.message);
              if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'print_result', success: false, error: err.message }));
              }
            });
          break;

        case 'open_drawer':
          console.log('💰 Open drawer command received');
          sendToPrinter(buildDrawerCmd())
            .then(() => {
              console.log('✅ Drawer opened');
              if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'print_result', success: true }));
              }
            })
            .catch((err) => {
              console.error('❌ Drawer failed:', err.message);
              if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'print_result', success: false, error: err.message }));
              }
            });
          break;

        case 'get_info':
          // Server requesting printer info
          const info = getPrinterInfo();
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
              type: 'printer_info',
              printer: info.printer,
              printer_type: info.type,
              usb_detected: info.usbDetected,
              version: VERSION
            }));
          }
          break;

        default:
          console.log('Unknown message:', msg.type);
      }
    } catch (e) {
      console.error('Message parse error:', e.message);
    }
  });

  ws.on('close', (code, reason) => {
    console.log(`🔌 Disconnected (code: ${code})${reason ? ': ' + reason : ''}`);
    clearInterval(heartbeatInterval);
    ws = null;

    if (!isShuttingDown) {
      const delay = Math.min(1000 * Math.pow(2, reconnectAttempt), 30000);
      reconnectAttempt++;
      console.log(`🔄 Reconnecting in ${delay / 1000}s (attempt ${reconnectAttempt})`);
      reconnectTimer = setTimeout(connectTunnel, delay);
    }
  });

  ws.on('error', (err) => {
    console.error('WebSocket error:', err.message);
  });
}

function getPrinterInfo() {
  const cfg = loadConfig();
  let usbDetected = false;
  if (USB) {
    try { usbDetected = !!USB.findPrinter(); } catch(e) {}
  }
  return {
    printer: cfg.printer_type === 'usb' ? 'USB' : `${cfg.printer_host}:${cfg.printer_port}`,
    type: cfg.printer_type,
    usbDetected
  };
}

// ── Optional: local HTTP fallback for debug ──
function startLocalServer() {
  const cfg = loadConfig();
  const server = http.createServer(async (req, res) => {
    const cors = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };
    if (req.method === 'OPTIONS') {
      res.writeHead(204, cors);
      return res.end();
    }
    const body = await new Promise((r) => { let d = ''; req.on('data', c => d += c); req.on('end', () => r(d)); });
    try {
      const data = body ? JSON.parse(body) : {};
      switch (req.url) {
        case '/status':
        case '/status/detail':
          const pinfo = getPrinterInfo();
          res.writeHead(200, { ...cors, 'Content-Type': 'application/json' });
          return res.end(JSON.stringify({ ok: true, status: 'running', printer: pinfo.printer, type: pinfo.type, usb_detected: pinfo.usbDetected }));
        case '/print/ticket':
          await sendToPrinter(buildESCPOS(data.text || ''));
          res.writeHead(200, { ...cors, 'Content-Type': 'application/json' });
          return res.end(JSON.stringify({ ok: true }));
        case '/print/open-drawer':
          await sendToPrinter(buildDrawerCmd());
          res.writeHead(200, { ...cors, 'Content-Type': 'application/json' });
          return res.end(JSON.stringify({ ok: true }));
        case '/print/test':
          await sendToPrinter(buildESCPOS('TEST DE IMPRESION\nTechExpert TPV\n\nSi ves esto, la impresora funciona!\n'));
          res.writeHead(200, { ...cors, 'Content-Type': 'application/json' });
          return res.end(JSON.stringify({ ok: true }));
        default:
          res.writeHead(404, cors);
          return res.end(JSON.stringify({ error: 'Not found' }));
      }
    } catch(e) {
      res.writeHead(500, { ...cors, 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({ error: e.message }));
    }
  });
  server.listen(cfg.agent_port, '127.0.0.1', () => {
    console.log(`Local fallback HTTP on http://127.0.0.1:${cfg.agent_port}`);
  });
}

// ── Main ──
const useLocal = process.argv.includes('--local');

console.log('');
console.log('╔══════════════════════════════════╗');
console.log('║   TechExpert TPV — Printer Agent ║');
console.log('║   Version ' + VERSION.padEnd(23) + '║');
console.log('╚══════════════════════════════════╝');
console.log('');

const cfg = loadConfig();
console.log(`Tunnel:     ${cfg.tunnel_url}`);
console.log(`Token:      ${cfg.token ? cfg.token.substring(0, 16) + '...' : '⚠️  NOT SET'}`);
console.log(`Type:       ${cfg.printer_type}`);
console.log(`Host/Port:  ${cfg.printer_host}:${cfg.printer_port}`);
if (USB) {
  const d = USB.findPrinter();
  console.log(`USB:        ${d ? '✅ DETECTED' : '❌ Not found'}`);
}
if (useLocal) {
  console.log(`\n⚠️  --local mode: HTTP fallback enabled on :${cfg.agent_port}`);
}
console.log('');

if (useLocal) {
  startLocalServer();
}

// Connect to tunnel (always connect unless explicit --no-tunnel)
if (!process.argv.includes('--no-tunnel')) {
  connectTunnel();
}

// Graceful shutdown
process.on('SIGINT', () => {
  isShuttingDown = true;
  console.log('\nShutting down...');
  clearInterval(heartbeatInterval);
  clearTimeout(reconnectTimer);
  if (ws) ws.close();
  process.exit(0);
});

process.on('SIGTERM', () => {
  isShuttingDown = true;
  clearInterval(heartbeatInterval);
  clearTimeout(reconnectTimer);
  if (ws) ws.close();
  process.exit(0);
});
