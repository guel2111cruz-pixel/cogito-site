'use strict';
const $ = id => document.getElementById(id);
const passwords = ['12345678', 'password', 'qwerty12', 'cogito26'];
let credential = ''; // Never persisted, included in URL, or cached.
let pending = null;
let busy = false;
try {
  const value = JSON.parse(localStorage.getItem('scct-pending'));
  if (value && /^[0-9a-f-]{36}$/.test(value.id) && Number.isInteger(value.choice) && value.choice >= 0 && value.choice < passwords.length) pending = value;
} catch { /* Storage unavailable or invalid: keep the app usable. */ }
function message(text) { $('status').textContent = text; }
function save() {
  try {
    if (pending) localStorage.setItem('scct-pending', JSON.stringify(pending));
    else localStorage.removeItem('scct-pending');
    return true;
  } catch { return false; }
}
function render() {
  $('choose').hidden = !!pending;
  $('waiting').hidden = !pending;
  $('controls').hidden = !credential;
  $('send').disabled = busy || !pending;
  $('cancel').disabled = busy;
  $('unlock').disabled = busy;
  $('lock').disabled = busy;
  $('next').disabled = busy || !!pending && pending.state !== 'applied';
}
passwords.forEach((password, choice) => {
  const button = document.createElement('button');
  button.textContent = password;
  button.addEventListener('click', () => {
    if (pending || busy) return;
    pending = {id: crypto.randomUUID(), choice, state: 'pending'};
    const stored = save();
    render(); $('waiting').setAttribute('tabindex', '-1'); $('waiting').focus();
    message(stored ? 'Escolha guardada neste tablet. Aguardando confirmação da placa.' : 'Escolha somente em memória. Mantenha o app aberto; o armazenamento está indisponível.');
    if (credential) apply();
  });
  $('options').append(button);
});
async function api(path, body) {
  const response = await fetch(path, {method: body ? 'POST' : 'GET', headers: {'Authorization': `Bearer ${credential}`, ...(body ? {'Content-Type':'application/json'} : {})}, ...(body ? {body:JSON.stringify(body)} : {}), cache:'no-store', signal:AbortSignal.timeout(20000)});
  const data = await response.json();
  if (!response.ok) throw new Error(response.status === 401 ? 'Código recusado. Autorize novamente.' : data.error || 'Ponte indisponível.');
  return data;
}
$('unlock').addEventListener('click', async () => {
  if (busy) return;
  busy = true; render();
  credential = $('token').value; $('token').value = '';
  try { await api('/api/health'); render(); message('Sessão autorizada. Feche a área da equipe antes de entregar o tablet.'); }
  catch (e) { credential = ''; render(); message(e.message); }
  finally { busy = false; render(); }
});
async function apply() {
  if (!pending || !credential || busy || pending.state === 'applied') return;
  busy = true; render(); message('Aguardando aplicação e confirmação da placa…');
  try {
    const result = await api('/api/select', {id:pending.id, choice:pending.choice});
    if (result.id !== pending.id || result.state !== 'applied') throw new Error('Resposta sem confirmação de aplicação.');
    pending.state = 'applied'; save(); message('Placa confirmou: senha aplicada. Clientes do AP precisam reconectar.');
  } catch (e) { message(`${e.message} Estado incerto: reconecte e toque em aplicar/verificar para consultar a mesma escolha.`); }
  finally { busy = false; render(); }
}
$('send').addEventListener('click', apply);
function clear() { pending = null; save(); render(); message('Aguardando escolha.'); }
$('cancel').addEventListener('click', () => {
  if (confirm('Descartar somente a escolha local? Isso não desfaz uma mudança já aplicada na placa.')) clear();
});
$('next').addEventListener('click', () => { if (!pending || pending.state === 'applied') { clear(); $('operator').open = false; } });
$('lock').addEventListener('click', () => { credential = ''; render(); message('Sessão encerrada. A escolha local foi mantida.'); });
render();
if (pending) message(pending.state === 'applied' ? 'Esta escolha recebeu confirmação da placa. Prepare o próximo participante.' : 'Escolha recuperada. Autorize a sessão e verifique com a placa.');
if ('serviceWorker' in navigator && isSecureContext) {
  navigator.serviceWorker.register('./sw.js').then(async () => {
    await navigator.serviceWorker.ready;
    $('cache').textContent = 'Interface preparada para uso offline. Controle requer a ponte local.';
  }).catch(() => { $('cache').textContent = 'Offline ainda não preparado. Reabra conectado e tente novamente.'; });
} else $('cache').textContent = 'Instalação offline requer HTTPS confiável ou localhost.';
