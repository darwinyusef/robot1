/* Conexion del visor con el ESP32 (firmware en ../esp32/brazo_v2_esp32). Dos vias, mismos comandos de texto (ver el .ino):
   - WiFi directo: WebSocket a ws://192.168.4.1:81 (red BrazoV2).
   - MQTT: wss://mqtt.aquicreamos.com; publica en <base>/cmd, escucha <base>/evt, <base>/state y <base>/status. Usuario/clave no se guardan.
   - Espejo en vivo: cada cuadro del visor (animacion o sliders) se manda como "P yaw th psi phi" a ~25 Hz.
   - Ejecutar en el ESP32: "PLAY id", el brazo reproduce la animacion por su cuenta (sin el visor). */
(function () {
  var sock = null, mq = null, mqBase = '', mirror = false, lastSend = 0, lastPose = '';
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

  function connect() {
    if (sock) { sock.close(); return; }
    var url = el('espUrl').value.trim();
    try { sock = new WebSocket(url); } catch (e) { status('URL invalida', false); sock = null; return; }
    status('conectando...', false);
    sock.onopen = function () { up(); };
    sock.onmessage = function (ev) { onMsg(String(ev.data)); };
    sock.onclose = function () { sock = null; down(); };
    sock.onerror = function () { status('error de conexion (red BrazoV2?)', false); };
  }

  function up() { status('conectado', true); el('espBtn').textContent = 'Desconectar'; el('espCtl').style.display = ''; }
  function down() { stopMirror(); status('desconectado', false); el('espBtn').textContent = 'Conectar'; el('espCtl').style.display = 'none'; }
  function onMsg(m) {
    if (m.indexOf('ANIMS ') === 0) buildButtons(m.slice(6).split(','));
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
  el('espVia').onchange = function () {
    var m = this.value === 'mqtt';
    el('espMq').style.display = m ? '' : 'none';
    el('espUrl').value = m ? 'wss://mqtt.aquicreamos.com' : 'ws://192.168.4.1:81';
    status('desconectado', false);
  };
  el('espMirror').onchange = function () { mirror = this.checked; lastPose = ''; };
  el('espStop').onclick = function () { stopMirror(); send('STOP'); };
  el('espHome').onclick = function () { stopMirror(); send('HOME'); };
  el('espTour').onclick = function () { stopMirror(); send('TOUR'); };

  window.ESP = {
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
