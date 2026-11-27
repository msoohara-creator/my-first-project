'use strict';
/* ミミドク — データはすべてこの端末のブラウザ内 (localStorage) に保存されます */

const KEY = 'mimidoku-v1';
const SERVICES = {
  audiobookjp: { name: 'audiobook.jp', home: 'https://audiobook.jp/', search: q => 'https://audiobook.jp/search?q=' + encodeURIComponent(q) },
  audible: { name: 'Audible', home: 'https://www.audible.co.jp/', search: q => 'https://www.audible.co.jp/search?keywords=' + encodeURIComponent(q) },
};

const defaults = () => ({
  books: [],          // 配列の順番 = 聴く順番
  logs: {},           // { 'YYYY-MM-DD': 分 }
  lastLog: null,      // 取り消し用
  settings: { goal: 15, remindAt: '21:00', notify: false },
  notifiedOn: '',
});

let state = load();
let tab = 'today';
let listFilter = 'queue';
let draft = null;     // 追加フォームの初期値（共有から開いたとき）

function load() {
  try {
    const s = JSON.parse(localStorage.getItem(KEY));
    if (s && Array.isArray(s.books)) return { ...defaults(), ...s, settings: { ...defaults().settings, ...s.settings } };
  } catch (e) { /* 壊れていたら初期化 */ }
  return defaults();
}
function save() {
  try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { toast('保存できませんでした'); }
}

/* ---------- ユーティリティ ---------- */
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const pad = n => String(n).padStart(2, '0');
const dkey = (d = new Date()) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const fmtMin = m => { m = Math.round(m); const h = Math.floor(m / 60), r = m % 60; return h ? (r ? `${h}時間${r}分` : `${h}時間`) : `${r}分`; };
const safeUrl = u => /^https?:\/\//i.test(u || '') ? u : '';
const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);

function detectService(url) {
  if (/audible\./i.test(url)) return 'audible';
  if (/audiobook\.jp/i.test(url)) return 'audiobookjp';
  return '';
}
function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove('show'), 2200);
}

/* ---------- 集計 ---------- */
const todayMin = () => state.logs[dkey()] || 0;
const current = () => state.books.find(b => b.status === 'listening');
const queue = () => state.books.filter(b => b.status !== 'done');
const remaining = b => Math.max(0, (b.minutes || 0) - (b.listened || 0));

function streak() {
  let d = new Date(), n = 0;
  if (!state.logs[dkey(d)]) d = addDays(d, -1);   // 今日まだでも昨日までの連続は生きている
  while (state.logs[dkey(d)] > 0) { n++; d = addDays(d, -1); }
  return n;
}
function bestStreak() {
  const days = Object.keys(state.logs).filter(k => state.logs[k] > 0).sort();
  let best = 0, run = 0, prev = null;
  for (const k of days) {
    run = prev && dkey(addDays(new Date(prev + 'T00:00'), 1)) === k ? run + 1 : 1;
    best = Math.max(best, run); prev = k;
  }
  return best;
}
function recentPace(n = 14) {
  let sum = 0;
  for (let i = 0; i < n; i++) sum += state.logs[dkey(addDays(new Date(), -i))] || 0;
  return sum / n;
}

/* ---------- 操作 ---------- */
function logMinutes(m) {
  m = Math.round(Number(m));
  if (!m || m < 1 || m > 1440) return toast('1〜1440分で入力してください');
  const first = !todayMin();
  const k = dkey(), b = current();
  state.logs[k] = (state.logs[k] || 0) + m;
  state.lastLog = { date: k, m, bookId: b ? b.id : null };
  if (b) b.listened = (b.listened || 0) + m;
  save(); render();
  toast(first ? `ナイス！ ${streak()}日連続です 🔥` : `+${m}分 記録しました`);
}
function undoLog() {
  const l = state.lastLog; if (!l) return;
  state.logs[l.date] = Math.max(0, (state.logs[l.date] || 0) - l.m);
  if (!state.logs[l.date]) delete state.logs[l.date];
  const b = state.books.find(x => x.id === l.bookId);
  if (b) b.listened = Math.max(0, (b.listened || 0) - l.m);
  state.lastLog = null; save(); render(); toast('取り消しました');
}
function startBook(id) {
  state.books.forEach(b => { if (b.status === 'listening') b.status = 'queue'; });
  const i = state.books.findIndex(b => b.id === id); if (i < 0) return;
  const [b] = state.books.splice(i, 1);
  b.status = 'listening'; state.books.unshift(b);
  save(); render(); toast('「' + b.title + '」を聴き始めます');
}
function finishBook(id) {
  const b = state.books.find(x => x.id === id); if (!b) return;
  b.status = 'done'; b.finishedAt = dkey();
  if (b.minutes) b.listened = b.minutes;
  save(); render(); toast('聴了おめでとうございます 🎉');
}
function moveBook(id, dir) {
  const q = queue(), i = q.findIndex(b => b.id === id), j = i + dir;
  if (i < 0 || j < 0 || j >= q.length) return;
  const a = state.books.indexOf(q[i]), c = state.books.indexOf(q[j]);
  [state.books[a], state.books[c]] = [state.books[c], state.books[a]];
  save(); render();
}
function addBook(f) {
  const title = f.title.value.trim();
  if (!title) return toast('タイトルを入力してください');
  const url = safeUrl(f.url.value.trim());
  const minutes = (Number(f.h.value) || 0) * 60 + (Number(f.m.value) || 0);
  state.books.push({
    id: uid(), title, author: f.author.value.trim(), url,
    service: f.service.value || detectService(url) || 'audiobookjp',
    minutes, listened: 0, status: 'queue', addedAt: dkey(),
  });
  draft = null; save(); render(); toast('リストに追加しました');
}

/* ---------- 画面 ---------- */
function bookMeta(b) {
  const parts = [];
  if (b.author) parts.push(esc(b.author));
  if (b.minutes) parts.push(b.status === 'done' ? fmtMin(b.minutes) : `残り ${fmtMin(remaining(b))}`);
  return `<span class="badge ${b.service}">${SERVICES[b.service].name}</span> <span class="muted">${parts.join(' ・ ')}</span>`;
}
const openLink = (b, label, cls = 'btn small') =>
  `<a class="${cls}" target="_blank" rel="noopener" href="${esc(b.url || SERVICES[b.service].home)}">${label}</a>`;

function viewToday() {
  const goal = state.settings.goal, t = todayMin(), pct = Math.min(1, t / goal), done = t >= goal;
  const C = 2 * Math.PI * 44, cur = current(), next = queue().filter(b => b !== cur).slice(0, 3);
  const now = new Date(), [rh, rm] = state.settings.remindAt.split(':').map(Number);
  const late = !t && (now.getHours() * 60 + now.getMinutes() >= rh * 60 + rm);
  const s = streak();
  const msg = done ? '今日の目標を達成しました！' : t ? `あと${goal - t}分で今日の目標達成` : late ? 'そろそろ耳読書の時間です' : '今日はまだ聴いていません';
  const sub = done ? 'おつかれさまでした。続きが気になれば、もう少しどうぞ。'
    : s ? `${s}日連続を${t ? '更新中' : '途切れさせないように、5分だけでも'}。` : 'まずは5分、通勤や家事のおともに。';

  let h = `<section class="card ${done ? 'done-today' : late ? 'nudge' : ''}">
    <div class="hero">
      <div class="ring"><svg width="104" height="104" viewBox="0 0 104 104">
        <circle cx="52" cy="52" r="44" fill="none" stroke="var(--h0)" stroke-width="10"/>
        <circle cx="52" cy="52" r="44" fill="none" stroke="${done ? 'var(--ok)' : 'var(--accent)'}" stroke-width="10" stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="${C * (1 - pct)}"/>
      </svg><div class="num">${t}<small>/ ${goal}分</small></div></div>
      <div class="grow"><h3>${msg}</h3><div class="muted">${sub}</div></div>
    </div>
    <div class="quick">
      <button class="btn" data-act="log" data-m="5">+5分</button>
      <button class="btn" data-act="log" data-m="15">+15分</button>
      <button class="btn" data-act="log" data-m="30">+30分</button>
    </div>
    <div class="row" style="margin-top:8px">
      <input class="grow" id="customMin" type="number" min="1" max="1440" inputmode="numeric" placeholder="分数を入力" style="flex-basis:120px">
      <button class="btn" data-act="logCustom">記録</button>
      ${state.lastLog ? '<button class="btn ghost" data-act="undo">直前を取り消す</button>' : ''}
    </div>
  </section>`;

  if (cur) {
    const p = cur.minutes ? Math.min(100, Math.round((cur.listened || 0) / cur.minutes * 100)) : 0;
    h += `<section class="card"><h2>いま聴いている本</h2>
      <div class="t" style="font-weight:700;font-size:17px">${esc(cur.title)}</div>
      <div>${bookMeta(cur)}</div>
      ${cur.minutes ? `<div class="bar"><i style="width:${p}%"></i></div><div class="muted">${p}% ・ ${fmtMin(cur.listened || 0)} / ${fmtMin(cur.minutes)}</div>` : ''}
      <div class="row" style="margin-top:10px">
        ${openLink(cur, '▶ ' + SERVICES[cur.service].name + ' で聴く', 'btn primary')}
        <button class="btn" data-act="finish" data-id="${cur.id}">聴き終えた</button>
      </div></section>`;
  } else if (next.length) {
    h += `<section class="card"><h2>次の1冊を選びましょう</h2>
      <div class="t" style="font-weight:700;font-size:17px">${esc(next[0].title)}</div><div>${bookMeta(next[0])}</div>
      <div class="row" style="margin-top:10px"><button class="btn primary" data-act="start" data-id="${next[0].id}">この本を聴き始める</button></div></section>`;
  } else {
    h += `<section class="card"><h2>はじめに</h2><p style="margin:0 0 10px">聴きたい本を「リスト」に追加すると、ここに次の1冊が表示されます。</p>
      <button class="btn primary" data-act="goto" data-tab="list">本を追加する</button></section>`;
  }

  const rest = cur ? next : next.slice(1);
  if (rest.length) {
    h += `<section class="card"><h2>このあと聴く本</h2>` +
      rest.map((b, i) => `<div class="book"><div class="pos">${i + 1}</div><div class="grow"><div class="t">${esc(b.title)}</div>${bookMeta(b)}</div></div>`).join('') +
      `<div class="muted" style="margin-top:6px">リスト全体：${queue().length}冊</div></section>`;
  }
  return h;
}

function viewList() {
  const q = queue(), done = state.books.filter(b => b.status === 'done').reverse();
  const d = draft || {};
  let h = `<section class="card"><h2>本を追加</h2>
    <form class="add" id="addForm" autocomplete="off">
      <label>作品ページのURL（任意・貼るとサービスを自動判別）<input name="url" type="url" inputmode="url" placeholder="https://audiobook.jp/… または https://www.audible.co.jp/…" value="${esc(d.url)}"></label>
      <label>タイトル<input name="title" type="text" required value="${esc(d.title)}"></label>
      <div class="two">
        <label>著者（任意）<input name="author" type="text"></label>
        <label>サービス<select name="service">
          <option value="audiobookjp" ${d.service === 'audiobookjp' ? 'selected' : ''}>audiobook.jp</option>
          <option value="audible" ${d.service === 'audible' ? 'selected' : ''}>Audible</option>
        </select></label>
      </div>
      <div class="two">
        <label>再生時間（時間）<input name="h" type="number" min="0" max="200" inputmode="numeric" placeholder="例: 6"></label>
        <label>（分）<input name="m" type="number" min="0" max="59" inputmode="numeric" placeholder="例: 30"></label>
      </div>
      <div class="row">
        <button class="btn primary" type="submit">リストに追加</button>
        <button class="btn small" type="button" data-act="search" data-s="audiobookjp">audiobook.jpで探す</button>
        <button class="btn small" type="button" data-act="search" data-s="audible">Audibleで探す</button>
      </div>
    </form></section>`;

  h += `<section class="card"><div class="seg">
      <button data-act="filter" data-f="queue" class="${listFilter === 'queue' ? 'on' : ''}">聴く順 (${q.length})</button>
      <button data-act="filter" data-f="audiobookjp" class="${listFilter === 'audiobookjp' ? 'on' : ''}">audiobook.jp</button>
      <button data-act="filter" data-f="audible" class="${listFilter === 'audible' ? 'on' : ''}">Audible</button>
      <button data-act="filter" data-f="done" class="${listFilter === 'done' ? 'on' : ''}">聴了 (${done.length})</button>
    </div>`;

  const rows = listFilter === 'done' ? done : listFilter === 'queue' ? q : q.filter(b => b.service === listFilter);
  if (!rows.length) h += `<p class="muted" style="margin:0">${listFilter === 'done' ? 'まだ聴き終えた本はありません。' : 'まだ本がありません。上のフォームから追加してください。'}</p>`;
  h += rows.map(b => {
    const pos = q.indexOf(b) + 1;
    const title = b.url ? `<a href="${esc(b.url)}" target="_blank" rel="noopener">${esc(b.title)}</a>` : esc(b.title);
    const acts = b.status === 'done'
      ? `<span class="muted">${esc(b.finishedAt || '')} 聴了</span> <button class="btn small ghost" data-act="del" data-id="${b.id}">削除</button>`
      : `${b.status === 'listening' ? '<span class="muted">再生中</span>' : `<button class="btn small" data-act="start" data-id="${b.id}">聴き始める</button>`}
         <button class="btn small" data-act="finish" data-id="${b.id}">聴了</button>
         ${listFilter === 'queue' ? `<button class="btn small" data-act="up" data-id="${b.id}" aria-label="上へ">▲</button><button class="btn small" data-act="down" data-id="${b.id}" aria-label="下へ">▼</button>` : ''}
         <button class="btn small ghost" data-act="del" data-id="${b.id}">削除</button>`;
    return `<div class="book ${b.status}"><div class="pos">${b.status === 'done' ? '✓' : pos}</div>
      <div class="grow"><div class="t">${title}</div>${bookMeta(b)}<div class="row acts">${acts}</div></div></div>`;
  }).join('');
  return h + '</section>';
}

function viewStats() {
  const goal = state.settings.goal;
  const total = Object.values(state.logs).reduce((a, b) => a + b, 0);
  const doneN = state.books.filter(b => b.status === 'done').length;
  const q = queue();
  const rem = { audiobookjp: 0, audible: 0 }, cnt = { audiobookjp: 0, audible: 0 };
  let unknown = 0;
  q.forEach(b => { cnt[b.service]++; if (b.minutes) rem[b.service] += remaining(b); else unknown++; });
  const remAll = rem.audiobookjp + rem.audible, pace = recentPace();
  const eta = p => { if (!p || !remAll) return '—'; const d = Math.ceil(remAll / p); return `約${d}日（${dkey(addDays(new Date(), d)).replace(/-/g, '/')}ごろ）`; };

  // ヒートマップ：直近17週、列=週(日曜始まり)
  const WEEKS = 17, today = new Date(), start = addDays(today, -(today.getDay() + 7 * (WEEKS - 1)));
  let cells = '';
  for (let i = 0; i < WEEKS * 7; i++) {
    const d = addDays(start, i), k = dkey(d), m = state.logs[k] || 0;
    const lv = !m ? '' : m >= goal * 2 ? 'l3' : m >= goal ? 'l2' : 'l1';
    cells += `<i class="${lv} ${k === dkey() ? 'today' : ''} ${d > today ? 'future' : ''}" title="${k}：${m}分"></i>`;
  }

  return `<section class="card"><h2>耳読書の記録</h2>
      <div class="stats">
        <div class="stat"><b>${streak()}</b><span>連続日数（最長 ${bestStreak()}）</span></div>
        <div class="stat"><b>${(total / 60).toFixed(1)}</b><span>累計 時間</span></div>
        <div class="stat"><b>${doneN}</b><span>聴了 冊</span></div>
      </div></section>
    <section class="card"><h2>直近17週間</h2><div class="heat">${cells}</div>
      <div class="legend">0分 <i style="background:var(--h0)"></i><i style="background:var(--h1)"></i><i style="background:var(--h2)"></i><i style="background:var(--h3)"></i> 目標の2倍〜</div></section>
    <section class="card"><h2>積読の残り時間</h2>
      ${remAll ? `<div class="stack"><i class="audiobookjp" style="width:${rem.audiobookjp / remAll * 100}%"></i><i class="audible" style="width:${rem.audible / remAll * 100}%"></i></div>` : ''}
      <p style="margin:10px 0 4px"><span class="dot" style="background:var(--abj)"></span>audiobook.jp：${cnt.audiobookjp}冊・${fmtMin(rem.audiobookjp)}</p>
      <p style="margin:0 0 10px"><span class="dot" style="background:var(--aud)"></span>Audible：${cnt.audible}冊・${fmtMin(rem.audible)}</p>
      ${unknown ? `<p class="muted">※再生時間が未入力の本が${unknown}冊あります（集計に含まれません）</p>` : ''}
      <p style="margin:0">目標どおり（1日${goal}分）なら：<b>${eta(goal)}</b></p>
      <p style="margin:0">直近14日のペース（1日${Math.round(pace)}分）なら：<b>${eta(pace)}</b></p>
    </section>`;
}

function viewSettings() {
  const s = state.settings;
  const perm = 'Notification' in window ? Notification.permission : 'unsupported';
  const nState = perm === 'unsupported' ? 'このブラウザは通知に対応していません' : perm === 'denied' ? '通知がブロックされています（ブラウザの設定で許可してください）' : s.notify && perm === 'granted' ? '通知オン' : '通知オフ';
  return `<section class="card"><h2>毎日の目標とリマインダー</h2>
      <div class="add" style="display:grid;gap:10px">
        <div class="two" style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
          <label>1日の目標（分）<input id="goal" type="number" min="1" max="600" inputmode="numeric" value="${s.goal}"></label>
          <label>リマインド時刻<input id="remindAt" type="time" value="${esc(s.remindAt)}"></label>
        </div>
        <div class="row"><button class="btn ${s.notify && perm === 'granted' ? '' : 'primary'}" data-act="notify">${s.notify && perm === 'granted' ? '通知をオフにする' : '通知をオンにする'}</button><span class="muted">${nState}</span></div>
        <p class="muted" style="margin:0">アプリ内通知は、アプリ（ホーム画面に追加したもの）が開いているか裏で動いているときに届きます。確実に毎日届かせたい場合は、下のカレンダー登録がおすすめです。</p>
        <div class="row">
          <a class="btn" target="_blank" rel="noopener" href="${esc(gcalLink())}">Googleカレンダーに毎日の予定を追加</a>
          <button class="btn" data-act="ics">カレンダー用ファイル(.ics)</button>
        </div>
      </div></section>
    <section class="card"><h2>データ</h2>
      <p class="muted" style="margin-top:0">データはこの端末のブラウザ内だけに保存されます。機種変更やバックアップには書き出しを使ってください。</p>
      <div class="row">
        <button class="btn" data-act="export">書き出す（JSON）</button>
        <label class="btn" style="color:inherit;font-size:14px">読み込む<input id="importFile" type="file" accept="application/json,.json" hidden></label>
        <button class="btn ghost" data-act="reset">すべて消去</button>
      </div></section>
    <section class="card"><h2>使い方のヒント</h2>
      <ul style="margin:0;padding-left:1.2em;font-size:14px">
        <li>スマホではブラウザのメニューから「ホーム画面に追加」するとアプリのように使えます。</li>
        <li>Androidでは、ホーム画面に追加後、Audibleやaudiobook.jpの作品ページを「共有」→「ミミドク」で送ると追加フォームに自動入力されます。</li>
        <li>聴いたら「今日」タブで分数を記録。1日1回の記録が連続日数になります。</li>
      </ul></section>`;
}

function render() {
  const v = { today: viewToday, list: viewList, stats: viewStats, settings: viewSettings }[tab];
  $('#view').innerHTML = v();
  document.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === tab));
  const s = streak();
  $('#streakChip').textContent = `🔥 ${s}日連続${todayMin() ? ' ✓' : ''}`;
}

/* ---------- リマインダー ---------- */
function reminderTimes() {
  const [h, m] = state.settings.remindAt.split(':').map(Number);
  const s = new Date(); s.setHours(h, m, 0, 0);
  const f = d => `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}T${pad(d.getHours())}${pad(d.getMinutes())}00`;
  return [f(s), f(new Date(s.getTime() + state.settings.goal * 60000))];
}
function gcalLink() {
  const [a, b] = reminderTimes();
  const p = new URLSearchParams({
    action: 'TEMPLATE', text: '🎧 耳読書の時間', dates: `${a}/${b}`, recur: 'RRULE:FREQ=DAILY',
    details: `今日の耳読書（${state.settings.goal}分）\n${location.origin + location.pathname}`,
    ctz: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Tokyo',
  });
  return 'https://calendar.google.com/calendar/render?' + p;
}
function download(name, text, type) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
function downloadIcs() {
  const [a, b] = reminderTimes();
  download('mimidoku-reminder.ics', [
    'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//mimidoku//JA', 'BEGIN:VEVENT',
    `UID:mimidoku-${Date.now()}@local`, `DTSTAMP:${a}`, `DTSTART:${a}`, `DTEND:${b}`, 'RRULE:FREQ=DAILY',
    'SUMMARY:🎧 耳読書の時間', `DESCRIPTION:今日の耳読書（${state.settings.goal}分）`,
    'BEGIN:VALARM', 'ACTION:DISPLAY', 'DESCRIPTION:耳読書の時間です', 'TRIGGER:PT0M', 'END:VALARM',
    'END:VEVENT', 'END:VCALENDAR'].join('\r\n'), 'text/calendar');
}
async function toggleNotify() {
  if (!('Notification' in window)) return toast('このブラウザは通知に対応していません');
  if (state.settings.notify && Notification.permission === 'granted') { state.settings.notify = false; }
  else {
    const p = await Notification.requestPermission();
    if (p !== 'granted') { render(); return toast('通知が許可されませんでした'); }
    state.settings.notify = true;
    notify('通知をオンにしました', `毎日 ${state.settings.remindAt} にお知らせします`);
  }
  save(); render();
}
async function notify(title, body) {
  try {
    const reg = 'serviceWorker' in navigator && await navigator.serviceWorker.getRegistration();
    if (reg) return reg.showNotification(title, { body, icon: 'icon.svg', tag: 'mimidoku' });
    new Notification(title, { body, icon: 'icon.svg', tag: 'mimidoku' });
  } catch (e) { /* 通知不可の環境では何もしない */ }
}
function checkReminder() {
  const s = state.settings, now = new Date(), k = dkey();
  if (!s.notify || state.notifiedOn === k || todayMin()) return;
  if (!('Notification' in window) || Notification.permission !== 'granted') return;
  const [h, m] = s.remindAt.split(':').map(Number);
  if (now.getHours() * 60 + now.getMinutes() < h * 60 + m) return;
  state.notifiedOn = k; save();
  const cur = current(), st = streak();
  notify('🎧 耳読書の時間です', (cur ? `「${cur.title}」の続きを` : '次の1冊を') + `${s.goal}分だけ聴きませんか？` + (st ? `（${st}日連続中）` : ''));
}

/* ---------- イベント ---------- */
document.addEventListener('click', e => {
  const tb = e.target.closest('.tabs button');
  if (tb) { tab = tb.dataset.tab; render(); window.scrollTo(0, 0); return; }
  const el = e.target.closest('[data-act]'); if (!el) return;
  const { act, id } = el.dataset;
  switch (act) {
    case 'log': logMinutes(el.dataset.m); break;
    case 'logCustom': logMinutes($('#customMin').value); break;
    case 'undo': undoLog(); break;
    case 'start': startBook(id); break;
    case 'finish': finishBook(id); break;
    case 'up': moveBook(id, -1); break;
    case 'down': moveBook(id, 1); break;
    case 'del': {
      const b = state.books.find(x => x.id === id);
      if (b && confirm(`「${b.title}」をリストから削除しますか？`)) { state.books = state.books.filter(x => x.id !== id); save(); render(); }
      break;
    }
    case 'filter': listFilter = el.dataset.f; render(); break;
    case 'goto': tab = el.dataset.tab; render(); break;
    case 'search': {
      const q = $('#addForm').title.value.trim();
      window.open(q ? SERVICES[el.dataset.s].search(q) : SERVICES[el.dataset.s].home, '_blank', 'noopener');
      break;
    }
    case 'notify': toggleNotify(); break;
    case 'ics': downloadIcs(); break;
    case 'export': download(`mimidoku-${dkey()}.json`, JSON.stringify(state, null, 2), 'application/json'); break;
    case 'reset':
      if (confirm('すべての本と記録を消去します。よろしいですか？')) { state = defaults(); save(); render(); }
      break;
  }
});
document.addEventListener('submit', e => { if (e.target.id === 'addForm') { e.preventDefault(); addBook(e.target); } });
document.addEventListener('input', e => {
  if (e.target.name === 'url' && e.target.form?.id === 'addForm') {
    const s = detectService(e.target.value); if (s) e.target.form.service.value = s;
  }
});
document.addEventListener('change', e => {
  const t = e.target;
  if (t.id === 'goal') { const v = Math.round(Number(t.value)); if (v >= 1 && v <= 600) { state.settings.goal = v; save(); render(); } }
  if (t.id === 'remindAt' && /^\d\d:\d\d$/.test(t.value)) { state.settings.remindAt = t.value; state.notifiedOn = ''; save(); render(); }
  if (t.id === 'importFile' && t.files[0]) {
    t.files[0].text().then(txt => {
      const s = JSON.parse(txt);
      if (!s || !Array.isArray(s.books)) throw new Error('bad');
      if (!confirm(`${s.books.length}冊のデータを読み込み、現在のデータを置き換えます。よろしいですか？`)) return;
      localStorage.setItem(KEY, JSON.stringify(s)); state = load(); render(); toast('読み込みました');
    }).catch(() => toast('読み込めないファイルです'));
  }
});

/* ---------- 起動 ---------- */
(function init() {
  // 共有メニュー（Web Share Target）や ?url=…&title=… から開かれたとき
  const p = new URLSearchParams(location.search);
  if (p.has('title') || p.has('text') || p.has('url')) {
    const text = p.get('text') || '';
    const url = safeUrl(p.get('url') || (text.match(/https?:\/\/\S+/) || [''])[0]);
    const title = (p.get('title') || text.replace(/https?:\/\/\S+/g, '')).trim().slice(0, 200);
    draft = { url, title, service: detectService(url) };
    tab = 'list';
    history.replaceState(null, '', location.pathname);
  }
  render();
  if ('serviceWorker' in navigator && location.protocol !== 'file:') navigator.serviceWorker.register('sw.js').catch(() => {});
  checkReminder();
  setInterval(() => { checkReminder(); if (tab === 'today' && document.activeElement?.id !== 'customMin') render(); }, 60000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) { checkReminder(); if (tab !== 'list' && tab !== 'settings') render(); } });
})();
