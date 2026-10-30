const $ = (id) => document.getElementById(id);
const state = { status: null, draws: [], analysis: null, picks: [], savedTickets: [], historyPage: 0, historyPageSize: 20 };
const PAGE_TITLES = { overview: '数据总览', analysis: '统计分析', picker: '智能选号', backtest: '策略回测', history: '历史数据', tickets: '我的号码' };
const pad = (n) => String(n).padStart(2, '0');
const fmt = (v) => v === null || v === undefined || v === '' ? '—' : v;

function toast(message, error = false) {
  const el = $('toast'); el.textContent = message; el.className = `toast show${error ? ' error' : ''}`;
  clearTimeout(toast.timer); toast.timer = setTimeout(() => { el.className = 'toast'; }, 3200);
}
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function ballsHtml(red, blue, small = false) {
  return `<div class="${small ? 'small-balls' : 'balls-line'}">${red.map(n => `<span class="ball">${pad(n)}</span>`).join('')}<span class="plus">+</span><span class="ball blue">${pad(blue)}</span></div>`;
}
async function api(url, options = {}) {
  const response = await fetch(url, { headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }, ...options });
  let data = {};
  try { data = await response.json(); } catch (_) { data = {}; }
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === 'string' ? detail : (detail?.message || JSON.stringify(detail) || `HTTP ${response.status}`));
  }
  return data;
}

function navigate(tab) {
  document.querySelectorAll('.nav-item').forEach(btn => btn.classList.toggle('active', btn.dataset.tab === tab));
  document.querySelectorAll('.page').forEach(page => page.classList.toggle('active', page.id === `page-${tab}`));
  $('pageTitle').textContent = PAGE_TITLES[tab] || 'SSQ Lab';
  if (tab === 'analysis') loadAnalysis();
  if (tab === 'history') loadHistory();
  if (tab === 'tickets') renderTickets();
}
document.querySelectorAll('.nav-item').forEach(btn => btn.addEventListener('click', () => navigate(btn.dataset.tab)));
document.querySelectorAll('[data-goto]').forEach(btn => btn.addEventListener('click', () => navigate(btn.dataset.goto)));

async function loadStatus() {
  state.status = await api('/api/status');
  const s = state.status;
  $('totalDraws').textContent = s.draw_count.toLocaleString();
  $('latestIssueMini').textContent = s.latest?.issue || '—';
  $('latestIssue').textContent = s.latest ? `第 ${s.latest.issue} 期` : '等待同步数据';
  $('latestDate').textContent = s.latest?.draw_date || '—';
  $('latestBalls').innerHTML = s.latest ? ballsHtml(s.latest.red, s.latest.blue) : '<span class="empty-inline">同步后显示开奖号码</span>';
  $('syncTime').textContent = s.last_sync ? `数据更新于 ${new Date(s.last_sync).toLocaleString()}` : '尚未同步';
  $('sourceState').textContent = s.draw_count ? `已载入 ${s.draw_count} 期` : '等待数据同步';
  const sourceLabel = $('dataSourceLabel');
  if (sourceLabel) sourceLabel.textContent = s.source || '—';
  $('sourceDot').className = s.draw_count ? 'ok' : '';
  if (s.latest) {
    const all = await api('/api/draws?limit=10000&order=asc');
    state.draws = all.draws;
    const first = all.draws[0];
    $('dateRange').textContent = first ? `${first.draw_date.slice(0,4)}–${s.latest.draw_date.slice(0,4)}` : '—';
    renderRecent();
  } else {
    state.draws = [];
    $('dateRange').textContent = '—';
    renderRecent();
  }
  $('historyCount').textContent = `共 ${s.draw_count} 期 · 本地 SQLite 保存，按期号去重`;
}
function renderRecent() {
  const rows = state.draws.slice(-8).reverse();
  $('recentRows').innerHTML = rows.length ? rows.map(d => `<tr><td class="issue-cell">${escapeHtml(d.issue)}</td><td>${escapeHtml(d.draw_date)}</td><td>${ballsHtml(d.red, d.blue, true).replace(/<span class="plus">\+<\/span><span class="ball blue">\d+<\/span>/, '')}</td><td><span class="ball blue" style="width:22px;height:22px;font-size:9px">${pad(d.blue)}</span></td><td>${escapeHtml(d.sales || '—')}</td><td>${escapeHtml(d.poolmoney || '—')}</td></tr>`).join('') : '<tr><td colspan="6" class="empty-cell">暂无数据，请点击右上角同步开奖数据</td></tr>';
}

async function syncData(mode = 'incremental') {
  const btns = [$('syncBtn'), $('manualSyncBtn')].filter(Boolean);
  btns.forEach(b => { b.disabled = true; b.dataset.oldText = b.innerHTML; b.innerHTML = '同步中…'; });
  $('sourceState').textContent = '正在同步开奖数据…';
  try {
    const result = await api(`/api/sync?mode=${mode}`, { method: 'POST' });
    toast(result.message || '数据同步完成');
    await loadStatus();
    if ($('page-analysis').classList.contains('active')) await loadAnalysis();
    if ($('page-history').classList.contains('active')) await loadHistory();
  } catch (err) {
    $('sourceState').textContent = '同步失败';
    $('sourceDot').className = '';
    toast(err.message, true);
  } finally {
    btns.forEach(b => { b.disabled = false; b.innerHTML = b.dataset.oldText || '↻ 同步开奖数据'; });
  }
}
$('syncBtn').addEventListener('click', () => syncData(state.status?.draw_count ? 'incremental' : 'full'));
$('manualSyncBtn').addEventListener('click', () => syncData('incremental'));

function drawBarChart(target, frequency, maxNumber, blue = false) {
  const values = Array.from({length: maxNumber}, (_, i) => frequency?.[i + 1] || 0);
  const max = Math.max(1, ...values);
  $(target).innerHTML = values.map((v, i) => `<div class="bar-item"><div class="bar-track"><i class="bar-fill" style="height:${Math.max(v ? 4 : 0, v / max * 100)}%"></i></div><b>${pad(i + 1)}</b><small>${v}</small></div>`).join('');
}
function rankList(target, items, frequency, blue = false) {
  const max = Math.max(1, ...items.map(n => frequency[n] || 0));
  $(target).innerHTML = items.map((n, i) => `<div class="rank-row ${blue ? 'blue-rank' : ''}"><span class="rank-no">${pad(n)}</span><div class="rank-bar"><i style="width:${(frequency[n] || 0) / max * 100}%"></i></div><strong>${frequency[n] || 0}</strong></div>`).join('');
}
function renderStructure(metrics) {
  const odd = metrics.odd_even_distribution || {};
  const zones = metrics.zone_distribution || {};
  const oddTotal = Math.max(1, Object.values(odd).reduce((a,b)=>a+b,0));
  const zoneTotal = Math.max(1, Object.values(zones).reduce((a,b)=>a+b,0));
  const rows = (obj, total, label) => `<div class="structure-group"><strong>${label}</strong>${Object.entries(obj).sort((a,b)=>b[1]-a[1]).slice(0,6).map(([k,v]) => `<div class="structure-row"><span>${escapeHtml(k.replaceAll('-', ':'))}</span><div class="structure-bar"><i style="width:${v/total*100}%"></i></div><b>${v}</b></div>`).join('')}</div>`;
  $('structureBox').innerHTML = rows(odd, oddTotal, '奇数 : 偶数') + rows(zones, zoneTotal, '三区分布（01–11 / 12–22 / 23–33）');
}
async function loadAnalysis() {
  if (!state.draws.length) { toast('请先同步或导入历史开奖数据', true); return; }
  const win = $('analysisWindow').value;
  const data = await api(`/api/analysis?window=${win === 'all' ? 5000 : win}`);
  state.analysis = data;
  $('metricCount').textContent = data.window;
  $('metricSum').textContent = data.metrics.avg_sum;
  $('metricOdd').textContent = data.metrics.avg_odd;
  $('metricBlue').textContent = data.metrics.avg_blue;
  drawBarChart('redChart', data.red_frequency, 33);
  drawBarChart('blueChart', data.blue_frequency, 16, true);
  rankList('hotList', data.hot_red, data.red_frequency);
  const omissionOrder = Object.keys(data.red_omission).map(Number).sort((a,b) => data.red_omission[b] - data.red_omission[a]).slice(0,8);
  const maxOmit = Math.max(1, ...omissionOrder.map(n => data.red_omission[n]));
  $('omissionList').innerHTML = omissionOrder.map(n => `<div class="rank-row blue-rank"><span class="rank-no">${pad(n)}</span><div class="rank-bar"><i style="width:${data.red_omission[n]/maxOmit*100}%"></i></div><strong>${data.red_omission[n]}</strong></div>`).join('');
  $('frequencyRows').innerHTML = Array.from({length:33},(_,i)=>i+1).map(n => {
    const f = data.red_frequency[n] || 0, o = data.red_omission[n] || 0;
    const status = f >= data.metrics.average_red_frequency ? '<span class="frequency-status hot">窗口偏热</span>' : '<span class="frequency-status cold">窗口偏冷</span>';
    return `<tr><td><span class="ball" style="width:23px;height:23px;font-size:9px">${pad(n)}</span></td><td>${f}</td><td>${(f / Math.max(1,data.window) * 100).toFixed(1)}%</td><td>${o}</td><td>${status}</td></tr>`;
  }).join('');
  renderStructure(data.metrics);
}
$('analysisWindow').addEventListener('change', loadAnalysis);

function getPickWindow() { return $('pickWindow').value === 'all' ? 5000 : Number($('pickWindow').value); }
async function generatePicks() {
  const payload = {
    count: Number($('pickCount').value), mode: $('pickMode').value, window: getPickWindow(),
    sum_min: Number($('sumMin').value), sum_max: Number($('sumMax').value),
    use_filters: $('useFilters').checked, avoid_latest: $('avoidLatest').checked,
  };
  if (payload.sum_min > payload.sum_max) { toast('和值下限不能大于上限', true); return; }
  const btn = $('generateBtn'); btn.disabled = true; btn.textContent = '生成中…';
  try {
    const result = await api('/api/picks', { method: 'POST', body: JSON.stringify(payload) });
    state.picks = result.picks || [];
    renderPicks();
    $('pickSummary').textContent = `生成 ${state.picks.length} / ${result.requested} 注 · ${$('pickMode').selectedOptions[0].textContent}`;
    if (result.warning) toast(result.warning, true);
  } catch (err) { toast(err.message, true); }
  finally { btn.disabled = false; btn.textContent = '✳ 生成号码组合'; }
}
function renderPicks() {
  if (!state.picks.length) { $('pickResults').innerHTML = '<div class="empty-state"><div class="empty-symbol">✳</div><strong>没有生成结果</strong><span>请调整筛选条件</span></div>'; return; }
  $('pickResults').innerHTML = state.picks.map((p,i)=>`<div class="pick-row"><div class="pick-row-left"><span class="pick-index">${String(i+1).padStart(2,'0')}</span>${ballsHtml(p.red,p.blue)}</div><div class="pick-meta">和值 ${p.sum}<br>奇数 ${p.odd} · 三区 ${p.zones.join(':')}</div><div class="pick-actions"><button class="icon-btn" data-copy-pick="${i}">复制</button><button class="icon-btn" data-save-pick="${i}">保存</button></div></div>`).join('');
  document.querySelectorAll('[data-copy-pick]').forEach(btn => btn.addEventListener('click',()=>copyText(formatPick(state.picks[Number(btn.dataset.copyPick)]))));
  document.querySelectorAll('[data-save-pick]').forEach(btn => btn.addEventListener('click',()=>{ saveTicket(formatPick(state.picks[Number(btn.dataset.savePick)])); toast('已加入我的号码'); }));
}
function formatPick(p) { return `${p.red.map(pad).join(' ')} + ${pad(p.blue)}`; }
$('generateBtn').addEventListener('click', generatePicks);
$('copyPicksBtn').addEventListener('click',()=>copyText(state.picks.map(formatPick).join('\n')));
async function copyText(text) { if (!text) return toast('没有可复制的号码', true); try { await navigator.clipboard.writeText(text); toast('已复制到剪贴板'); } catch (_) { toast('浏览器未授予剪贴板权限，请手动复制', true); } }

async function runBacktest() {
  const btn = $('runBacktestBtn'); btn.disabled = true; btn.textContent = '回测中…';
  try {
    const result = await api(`/api/backtest?window=${$('backtestWindow').value}&warmup=100`);
    if (!result.results?.length) {
      $('backtestSummary').innerHTML = `<div class="empty-state"><div class="empty-symbol">⌁</div><strong>历史数据不足</strong><span>${escapeHtml(result.message || '请导入更多历史数据')}</span></div>`;
      $('backtestRows').innerHTML = '<tr><td colspan="8" class="empty-cell">暂无回测结果</td></tr>';
      return;
    }
    $('backtestSummary').innerHTML = `<div class="backtest-cards">${result.results.map(r=>`<div class="strategy-card"><strong>${r.name}</strong><span class="big">${r.hit_rate}%</span><small>中奖期数比例 · ${r.prize_draws}/${r.tested} 期</small></div>`).join('')}</div><p class="field-footnote">测试区间：${result.test_from} 至 ${result.test_to} · 共 ${result.sample_count} 期 · 训练窗口 ${result.window} 期。${escapeHtml(result.note)}</p>`;
    $('backtestRows').innerHTML = result.results.map(r=>`<tr><td><b>${r.name}</b></td><td>${r.tested}</td><td>${r.prize_draws}</td><td>${r.blue_hits}</td><td>${r.tiers['6']}</td><td>${r.tiers['5']}</td><td>${r.tiers['4']}</td><td>${r.tiers['3']+r.tiers['2']+r.tiers['1']}</td></tr>`).join('');
  } catch (err) { toast(err.message, true); }
  finally { btn.disabled = false; btn.textContent = '运行回测'; }
}
$('runBacktestBtn').addEventListener('click', runBacktest);

async function loadHistory() {
  const all = await api('/api/draws?limit=10000&order=desc');
  const rows = all.draws;
  state.historyRows = rows;
  const pages = Math.max(1, Math.ceil(rows.length / state.historyPageSize));
  state.historyPage = Math.min(state.historyPage, pages - 1);
  const start = state.historyPage * state.historyPageSize;
  const pageRows = rows.slice(start, start + state.historyPageSize);
  $('historyRows').innerHTML = pageRows.length ? pageRows.map(d=>`<tr><td class="issue-cell">${d.issue}</td><td>${d.draw_date}</td><td>${ballsHtml(d.red,d.blue,true).replace(/<span class="plus">\+<\/span><span class="ball blue">\d+<\/span>/,'')}</td><td><span class="ball blue" style="width:22px;height:22px;font-size:9px">${pad(d.blue)}</span></td><td>${escapeHtml(d.sales || '—')}</td><td>${escapeHtml(d.poolmoney || '—')}</td><td><span class="frequency-status hot">${escapeHtml(d.source || 'cwl.gov.cn')}</span></td></tr>`).join('') : '<tr><td colspan="7" class="empty-cell">暂无数据</td></tr>';
  $('historyPageInfo').textContent = `${rows.length ? start+1 : 0}–${Math.min(start+state.historyPageSize,rows.length)} / ${rows.length} 期`;
  $('prevPage').disabled = state.historyPage === 0;
  $('nextPage').disabled = state.historyPage >= pages - 1;
}
$('prevPage').addEventListener('click',()=>{state.historyPage=Math.max(0,state.historyPage-1);loadHistory();});
$('nextPage').addEventListener('click',()=>{state.historyPage++;loadHistory();});
$('exportBtn').addEventListener('click',()=>{window.location.href='/api/export.csv';});

function splitCsvLine(line) {
  const fields = []; let value = ''; let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (quoted && line[i + 1] === '"') { value += '"'; i++; }
      else quoted = !quoted;
    } else if (ch === ',' && !quoted) { fields.push(value); value = ''; }
    else value += ch;
  }
  fields.push(value);
  return fields;
}
function parseImportLine(line) {
  let s = line.trim().replace(/^\uFEFF/, ''); if (!s || s.startsWith('#')) return null;
  if (/^(issue|期号|期次|开奖期号)[,\s，]/i.test(s)) return null;
  const fields = splitCsvLine(s);
  if (fields.length >= 9 && /^20\d{5}$/.test(fields[0].trim()) && /20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}/.test(fields[1])) {
    const nums = fields.slice(2, 9).map(x => Number(String(x).trim()));
    if (nums.some(n => !Number.isFinite(n))) throw new Error(`号码字段不是数字：${line}`);
    return { code: fields[0].trim(), date: fields[1].trim().replaceAll('/','-').replaceAll('.','-'), red: nums.slice(0,6).join(','), blue: String(nums[6]), source: 'csv-import' };
  }
  let issue = '';
  const issueMatch = s.match(/\b20\d{5}\b/);
  if (issueMatch) { issue = issueMatch[0]; s = s.replace(issueMatch[0], ' '); }
  let date = '';
  const dateMatch = s.match(/20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}/);
  if (dateMatch) { date = dateMatch[0].replaceAll('/','-').replaceAll('.','-'); s = s.replace(dateMatch[0], ' '); }
  const nums = (s.match(/\d+/g) || []).map(Number);
  if (nums.length !== 7) throw new Error(`无法识别：${line}`);
  if (!issue || !date) throw new Error(`必须包含期号和开奖日期：${line}`);
  return { code: issue, date, red: nums.slice(0,6).join(','), blue: String(nums[6]), source: 'csv-import' };
}
$('importFile').addEventListener('change', async (event)=>{
  const file = event.target.files[0]; if (!file) return;
  try {
    const text = await file.text();
    const lines = text.split(/\r?\n/).filter(line => line.trim());
    const parsed = lines.map(parseImportLine).filter(Boolean);
    if (!parsed.length) throw new Error('文件中没有识别到有效数据行');
    await api('/api/import', { method:'POST', body: JSON.stringify({ draws: parsed, replace:false }) });
    toast(`成功导入 ${parsed.length} 期`); await loadStatus(); await loadHistory();
  } catch (err) { toast(err.message, true); }
  event.target.value = '';
});

function loadSavedTickets() {
  try { state.savedTickets = JSON.parse(localStorage.getItem('ssq_lab_tickets') || '[]'); }
  catch (_) { state.savedTickets = []; }
}
function persistTickets() { localStorage.setItem('ssq_lab_tickets', JSON.stringify(state.savedTickets)); }
function saveTicket(line) {
  if (!state.savedTickets.includes(line)) state.savedTickets.push(line);
  persistTickets();
}
function renderTickets() {
  loadSavedTickets();
  $('ticketInput').value = state.savedTickets.join('\n');
  const latest = state.status?.latest;
  if (!latest || !state.savedTickets.length) {
    $('ticketCompare').innerHTML = '<div class="empty-state compact"><div class="empty-symbol">♡</div><strong>等待号码</strong><span>保存号码后自动与最新一期比较</span></div>';
    return;
  }
  $('ticketCompareTitle').textContent = `对比第 ${latest.issue} 期 · ${latest.draw_date}`;
  const rows = state.savedTickets.map((line, idx)=>{
    const nums = (line.match(/\d+/g)||[]).map(Number); if (nums.length !== 7) return null;
    const red = nums.slice(0,6), blue = nums[6];
    const redHits = red.filter(n=>latest.red.includes(n)); const blueHit = blue === latest.blue;
    const tier = getPrizeTier(redHits.length, blueHit);
    return `<div class="compare-row"><div class="compare-row-top"><b>第 ${idx+1} 注</b><span class="compare-hit">${tier ? `中${tier}等奖` : `${redHits.length} 红${blueHit?' + 蓝':''}`}</span></div>${ballsHtml(red,blue,true)}<small style="display:block;color:#8e98a9;margin-top:7px">红球命中 ${redHits.length} 个${blueHit?'，蓝球命中':''} · ${tier ? '按规则达到中奖条件' : '未达到中奖条件'}</small></div>`;
  }).filter(Boolean).join('');
  $('ticketCompare').innerHTML = rows || '<div class="empty-cell">号码格式不正确</div>';
}
function getPrizeTier(r,b) { if(r===6&&b)return 1;if(r===6)return 2;if(r===5&&b)return 3;if(r===5||(r===4&&b))return 4;if(r===4||(r===3&&b))return 5;if(b)return 6;return null; }
$('saveTicketsBtn').addEventListener('click',()=>{
  const lines = $('ticketInput').value.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
  const parsed = [];
  for (const line of lines) {
    const nums = (line.match(/\d+/g)||[]).map(Number);
    if (nums.length!==7 || nums.slice(0,6).some(n=>n<1||n>33) || nums[6]<1||nums[6]>16 || new Set(nums.slice(0,6)).size!==6) { toast(`号码格式错误：${line}`,true); return; }
    parsed.push(`${nums.slice(0,6).sort((a,b)=>a-b).map(pad).join(' ')} + ${pad(nums[6])}`);
  }
  state.savedTickets = [...new Set(parsed)]; persistTickets(); renderTickets(); toast(`已保存 ${state.savedTickets.length} 注号码`);
});
$('addPicksBtn').addEventListener('click',()=>{ state.picks.forEach(p=>saveTicket(formatPick(p))); renderTickets(); toast(`已加入 ${state.picks.length} 注`); });
$('clearTicketsBtn').addEventListener('click',()=>{state.savedTickets=[];persistTickets();renderTickets();toast('已清空我的号码');});

async function boot() {
  loadSavedTickets();
  try {
    await loadStatus();
    const last = state.status.last_sync ? new Date(state.status.last_sync).getTime() : 0;
    const stale = !last || Date.now() - last > 24*60*60*1000;
    if (!state.status.draw_count || stale) await syncData(state.status.draw_count ? 'incremental' : 'full');
  } catch (err) { toast(`服务初始化失败：${err.message}`, true); }
}
boot();
