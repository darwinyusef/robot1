/* Conexion del visor con el ESP32 (firmware en ../esp32/brazo_v2_esp32). Tres vias, mismos comandos de texto (ver el .ino):
   - Hub (Docker, ../hub): WebSocket a /ws/client del hub; el ESP32 se conecta al mismo hub por WiFi. Pide el token del hub (no se guarda).
   - WiFi directo: WebSocket a ws://192.168.4.1:81 (red BrazoV2).
   - MQTT: wss://mqtt.aquicreamos.com; publica en <base>/cmd, escucha <base>/evt, <base>/state y <base>/status. Usuario/clave no se guardan.
   - Espejo en vivo: cada cuadro del visor (animacion o sliders) se manda como "P yaw th psi phi" a ~25 Hz.
   - Ejecutar en el ESP32: "PLAY id", el brazo reproduce la animacion por su cuenta (sin el visor). */
(function () {
  var wantHub = false, retryT = null, retries = 0;
  var sock = null, pingT = null, mq = null, mqBase = '', mirror = false, lastSend = 0, lastPose = '';
  var el = function (id) { return document.getElementById(id); };

  function status(s, ok) { var e = el('espStatus'); e.textContent = s; e.style.color = ok ? '#43d17a' : '#98a2b3'; }
  function send(s) {
    if (sock && sock.readyState === 1) sock.send(s);
    else if (mq && mq.connected) mq.publish(mqBase + '/cmd', s);
  }
  function stopMirror() { el('espMirror').checked = false; mirror = false; }

  function buildButtons(ids) {
    var box = el('espAnims'); box.innerHTML = '';
    ids.forEach(function (id) {
      var b = document.createElement('button'); b.textContent = id; b.onclick = function () { stopMirror(); send('PLAY ' + id); };
      box.appendChild(b);
    });
  }

  function hubUrl() {
    var u = el('espUrl').value.trim(), t = el('espTok').value;
    return u + (u.indexOf('?') < 0 ? '?' : '&') + 'token=' + encodeURIComponent(t);
  }

  function connect(auto) {
    if (sock) { wantHub = false; clearTimeout(retryT); sock.close(); return; }
    var hub = el('espVia').value === 'hub';
    if (auto !== true) retries = 0;
    wantHub = hub;
    var url = hub ? hubUrl() : el('espUrl').value.trim();
    try { sock = new WebSocket(url); } catch (e) { status('URL invalida', false); sock = null; return; }
    var me = sock;
    status('conectando...', false);
    me.onopen = function () {
      up(); retries = 0;
      if (hub) pingT = setInterval(function () { if (me.readyState === 1) me.send('PING'); }, 20000);
    };
    me.onmessage = function (ev) { onMsg(String(ev.data)); };
    me.onclose = function (ev) {
      clearInterval(pingT); if (sock === me) sock = null; down();
      if (ev && ev.code === 4401) status('token incorrecto', false);
      else if (ev && ev.code === 4408) status('el hub cerro por inactividad', false);
      if (wantHub && !(ev && ev.code === 4401) && retries < 10) {
        retries++; status('conexion perdida, reconectando (' + retries + '/10)...', false);
        retryT = setTimeout(function () { connect(true); }, 3000);
      } else wantHub = false;
    };
    me.onerror = function () { status(hub ? 'error de conexion con el hub' : 'error de conexion (red BrazoV2?)', false); };
  }

  function up() { status('conectado', true); el('espBtn').textContent = 'Desconectar'; el('espCtl').style.display = ''; }
  function down() { stopMirror(); status('desconectado', false); el('espBtn').textContent = 'Conectar'; el('espCtl').style.display = 'none'; }
  function onMsg(m) {
    if (m === 'PONG') return;
    if (m.indexOf('TP ') === 0) {
      var q = m.split(' ');
      if (window.ESPVIEW) window.ESPVIEW.pose({ yaw: +q[1], th: +q[2], psi: +q[3], phi: +q[4] });
      return;
    }
    if (m.indexOf('HUB ') === 0) status(m.slice(4).replace('esp32=online', 'brazo online').replace('esp32=offline', 'brazo OFFLINE'), m.indexOf('esp32=online') > 0);
    else if (m.indexOf('ANIMS ') === 0) buildButtons(m.slice(6).split(','));
    else if (m.indexOf('ERR') === 0 || m.indexOf('STATE') === 0 || m.indexOf('DONE') === 0) status(m, true);
  }

  function connectMqtt() {
    if (mq) { mq.end(true); mq = null; down(); return; }
    if (typeof mqtt === 'undefined') { status('falta lib/mqtt.min.js', false); return; }
    mqBase = el('espBase').value.trim().replace(/\/+$/, '') || 'brazo_v2';
    status('conectando a MQTT...', false);
    var c = mqtt.connect(el('espUrl').value.trim(), { username: el('espUser').value, password: el('espPass').value, reconnectPeriod: 3000, connectTimeout: 8000, clientId: 'visor_' + Math.random().toString(16).slice(2, 8) });
    mq = c;
    c.on('connect', function () {
      c.subscribe([mqBase + '/evt', mqBase + '/state', mqBase + '/status']);
      el('espBtn').textContent = 'Desconectar'; el('espCtl').style.display = '';
      status('MQTT conectado, esperando al brazo...', true);
      c.publish(mqBase + '/cmd', 'LIST');
    });
    c.on('message', function (t, payload) {
      var m = String(payload);
      if (t === mqBase + '/status') { status(m === 'online' ? 'brazo online' : 'brazo OFFLINE', m === 'online'); if (m === 'online') c.publish(mqBase + '/cmd', 'LIST'); }
      else onMsg(m);
    });
    c.on('close', function () { if (mq === c && !c.connected) status('MQTT sin conexion, reintentando...', false); });
    c.on('error', function (e) { status('MQTT error: ' + (e && e.message || e), false); });
  }

  el('espBtn').onclick = function () { (el('espVia').value === 'mqtt' ? connectMqtt : connect)(); };
  function hubDefault() {
    var h = location.protocol.indexOf('http') === 0 ? (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host : 'ws://localhost:8080';
    return h + '/ws/client?role=viewer';
  }
  el('espVia').onchange = function () {
    var v = this.value;
    el('espMq').style.display = v === 'mqtt' ? '' : 'none';
    el('espHub').style.display = v === 'hub' ? '' : 'none';
    el('espUrl').value = v === 'mqtt' ? 'wss://mqtt.aquicreamos.com' : v === 'hub' ? hubDefault() : 'ws://192.168.4.1:81';
    status('desconectado', false);
  };
  el('espVia').onchange();
  el('espMirror').onchange = function () { mirror = this.checked; lastPose = ''; };
  el('espStop').onclick = function () { stopMirror(); send('STOP'); };
  el('espHome').onclick = function () { stopMirror(); send('HOME'); };
  el('espOff').onclick = function () { stopMirror(); send('OFF'); };
  el('espTour').onclick = function () { stopMirror(); send('TOUR'); };
  Array.prototype.forEach.call(document.querySelectorAll('.espTest'), function (b) {
    b.onclick = function () { stopMirror(); send(b.dataset.t ? 'TEST ' + b.dataset.t : 'TEST'); };
  });

  window.ESP = {
    connected: function () { return !!((sock && sock.readyState === 1) || (mq && mq.connected)); },
    mirrorOn: function (on) { el('espMirror').checked = on; mirror = on; lastPose = ''; },
    pose: function (p) {
      if (!mirror) return;
      var now = performance.now();
      if (now - lastSend < 40) return;
      var s = 'P ' + p.yaw.toFixed(1) + ' ' + p.th.toFixed(1) + ' ' + p.psi.toFixed(1) + ' ' + p.phi.toFixed(1);
      if (s === lastPose) return;
      lastSend = now; lastPose = s; send(s);
    }
  };
})();
