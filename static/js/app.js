/* AirOS Log Analyzer  — Frontend */

let currentData = null;
let charts = { distribution: null, timeline: null, events: null };
let showRaw = false;

const COLORS = [
  '#6366f1', '#22c55e', '#eab308', '#ef4444', '#3b82f6',
  '#a855f7', '#ec4899', '#14b8a6', '#f97316', '#6b7280',
];

const TIMELINE_COLORS = {
  all: { border: '#6366f1', fill: 'rgba(99, 102, 241, 0.15)', point: '#6366f1' },
  warnings: { border: '#eab308', fill: 'rgba(234, 179, 8, 0.12)', point: '#eab308' },
  errors: { border: '#ef4444', fill: 'rgba(239, 68, 68, 0.12)', point: '#ef4444' },
};

document.addEventListener('DOMContentLoaded', () => {
  bindEvents();
  loadEmptyState();
});

function bindEvents() {
  const fileInputs = [document.getElementById('file-input'), document.getElementById('file-input-empty')];
  fileInputs.forEach(input => {
    if (input) input.addEventListener('change', e => {
      if (e.target.files[0]) uploadFile(e.target.files[0]);
    });
  });

  document.getElementById('btn-upload')?.addEventListener('click', () => {
    document.getElementById('file-input').click();
  });

  ['btn-fetch-modal', 'btn-fetch-empty'].forEach(id => {
    document.getElementById(id)?.addEventListener('click', e => {
      e.preventDefault();
      openModal();
    });
  });

  document.getElementById('modal-close')?.addEventListener('click', closeModal);
  document.getElementById('modal-cancel')?.addEventListener('click', closeModal);
  document.getElementById('modal-fetch')?.addEventListener('click', fetchFromDevice);

  document.getElementById('table-search')?.addEventListener('input', renderTable);
  document.getElementById('table-filter')?.addEventListener('change', renderTable);
  document.getElementById('btn-table-export')?.addEventListener('click', exportTable);
  document.getElementById('btn-export')?.addEventListener('click', exportReport);
  document.getElementById('btn-toggle-raw')?.addEventListener('click', toggleRawView);
}

function toggleRawView() {
  showRaw = !showRaw;
  const btn = document.getElementById('btn-toggle-raw');
  const header = document.getElementById('col-desc-header');
  btn.textContent = showRaw ? 'Açıklama' : 'Ham Log';
  header.textContent = showRaw ? 'Ham Log' : 'Açıklama';
  renderTable();
}

async function loadEmptyState() {
  showDashboard(false);
}

function showDashboard(loaded) {
  document.getElementById('empty-state').classList.toggle('hidden', loaded);
  document.getElementById('dashboard-content').classList.toggle('hidden', !loaded);
  document.getElementById('btn-export').disabled = !loaded;

  const status = document.getElementById('device-status');
  if (loaded) {
    status.textContent = 'Aktif';
    status.className = 'badge active';
  } else {
    status.textContent = 'Bekliyor';
    status.className = 'badge inactive';
  }
}

async function uploadFile(file) {
  const form = new FormData();
  form.append('file', file);
  showToast('Dosya analiz ediliyor...', 'success');

  try {
    const resp = await fetch('/api/analyze', { method: 'POST', body: form });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || 'Analiz hatası');
    applyData(data);
    showToast(`${file.name} başarıyla yüklendi — ${data.summary.total} kayıt analiz edildi.`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function fetchFromDevice() {
  const ip = document.getElementById('fetch-ip').value.trim();
  const username = document.getElementById('fetch-user').value.trim();
  const password = document.getElementById('fetch-pass').value;

  if (!ip) { showToast('IP adresi girmeniz gerekiyor.', 'error'); return; }

  document.getElementById('modal-loading').classList.remove('hidden');

  try {
    const resp = await fetch('/api/fetch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ip, username, password }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || 'Bağlantı hatası');
    applyData(data);
    closeModal();
    showToast(`${ip} cihazından ${data.summary.total} kayıt alındı.`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    document.getElementById('modal-loading').classList.add('hidden');
  }
}

function applyData(data) {
  currentData = data;
  showRaw = false;
  document.getElementById('btn-toggle-raw').textContent = 'Ham Log';
  document.getElementById('col-desc-header').textContent = 'Açıklama';
  showDashboard(true);

  document.getElementById('source-label').textContent = data.source || 'Log analizi tamamlandı';

  const s = data.summary;
  document.getElementById('kpi-total').textContent = s.total.toLocaleString('tr-TR');
  document.getElementById('kpi-info').innerHTML = `${s.info.toLocaleString('tr-TR')} <small id="kpi-info-pct">${s.info_pct}%</small>`;
  document.getElementById('kpi-warning').innerHTML = `${s.warning.toLocaleString('tr-TR')} <small id="kpi-warning-pct">${s.warning_pct}%</small>`;
  document.getElementById('kpi-error').innerHTML = `${s.error.toLocaleString('tr-TR')} <small id="kpi-error-pct">${s.error_pct}%</small>`;

  const dev = data.device || {};
  document.getElementById('kpi-device').textContent = dev.device || '—';
  document.getElementById('kpi-device-version').textContent = dev.version || '—';
  document.getElementById('dev-name').textContent = dev.device || '—';
  document.getElementById('dev-ip').textContent = dev.ip || '—';
  document.getElementById('dev-version').textContent = dev.version || '—';
  document.getElementById('dev-uptime').textContent = dev.uptime || '—';

  renderCharts(data);
  renderTable();
  renderProblems(data.problems);
}

function buildTimelineDataset(label, data, colorKey) {
  const c = TIMELINE_COLORS[colorKey];
  return {
    label,
    data,
    borderColor: c.border,
    backgroundColor: c.fill,
    pointBackgroundColor: c.point,
    pointBorderColor: '#0f1117',
    pointBorderWidth: 2,
    pointRadius: 5,
    pointHoverRadius: 7,
    fill: true,
    tension: 0.3,
  };
}

function renderCharts(data) {
  Chart.defaults.color = '#9ca3af';
  Chart.defaults.borderColor = '#2a2d3e';
  Chart.defaults.font.family = 'Inter, sans-serif';

  if (charts.distribution) charts.distribution.destroy();
  if (charts.timeline) charts.timeline.destroy();
  if (charts.events) charts.events.destroy();

  const dist = data.distribution;
  charts.distribution = new Chart(document.getElementById('chart-distribution'), {
    type: 'doughnut',
    data: {
      labels: dist.labels,
      datasets: [{
        data: dist.values,
        backgroundColor: COLORS.slice(0, dist.labels.length),
        borderWidth: 0,
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '65%',
      plugins: {
        legend: {
          position: 'right',
          labels: { boxWidth: 12, padding: 10, font: { size: 11 } },
        },
        tooltip: {
          callbacks: {
            label: ctx => {
              const pct = dist.percentages[ctx.dataIndex] || 0;
              return ` ${ctx.label}: ${ctx.raw} (${pct}%)`;
            },
          },
        },
      },
    },
  });

  const tl = data.timeline;
  charts.timeline = new Chart(document.getElementById('chart-timeline'), {
    type: 'line',
    data: {
      labels: tl.labels,
      datasets: [
        buildTimelineDataset('Tüm Olaylar', tl.all, 'all'),
        buildTimelineDataset('Uyarılar', tl.warnings, 'warnings'),
        buildTimelineDataset('Hatalar', tl.errors, 'errors'),
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            title: items => `Saat: ${items[0]?.label || ''}`,
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            maxTicksLimit: 12,
            maxRotation: 45,
            minRotation: 0,
          },
        },
        y: { beginAtZero: true, ticks: { stepSize: 1 } },
      },
    },
  });

  const top = data.top_events.filter(e => e.count > 0);
  charts.events = new Chart(document.getElementById('chart-events'), {
    type: 'bar',
    data: {
      labels: top.map(e => e.name),
      datasets: [{
        data: top.map(e => e.count),
        backgroundColor: COLORS.slice(0, top.length),
        borderRadius: 4,
        barThickness: 18,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, ticks: { stepSize: 1 } },
        y: { grid: { display: false } },
      },
    },
  });
}

function renderTable() {
  const tbody = document.getElementById('log-table-body');
  if (!currentData || !currentData.entries) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:40px;color:#6b7280">Veri yok</td></tr>';
    return;
  }

  const search = (document.getElementById('table-search')?.value || '').toLowerCase();
  const filter = document.getElementById('table-filter')?.value || 'all';

  let entries = currentData.entries;
  if (filter !== 'all') entries = entries.filter(e => e.level === filter);
  if (search) {
    entries = entries.filter(e =>
      e.explanation_tr.toLowerCase().includes(search) ||
      e.event.toLowerCase().includes(search) ||
      e.raw.toLowerCase().includes(search) ||
      e.level.toLowerCase().includes(search)
    );
  }

  if (entries.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:40px;color:#6b7280">Eşleşen kayıt bulunamadı</td></tr>';
    return;
  }

  tbody.innerHTML = entries.map(e => {
    const descContent = showRaw ? e.raw : e.explanation_tr;
    const descClass = showRaw ? 'col-description col-raw-mode' : 'col-description';
    return `
    <tr>
      <td class="col-time">${esc(e.time)}</td>
      <td><span class="level-badge ${e.level}">${e.level}</span></td>
      <td class="col-event">${esc(e.event)}</td>
      <td class="${descClass}">${esc(descContent)}</td>
    </tr>`;
  }).join('');
}

function renderProblems(problems) {
  const container = document.getElementById('problems-list');
  if (!problems || !problems.length) {
    container.innerHTML = '<div style="padding:20px;color:#6b7280;text-align:center">Analiz için log yükleyin</div>';
    return;
  }

  const icons = { ok: '✓', warning: '⚠', error: '✕', info: 'ℹ' };

  container.innerHTML = problems.map(p => `
    <div class="problem-item">
      <div class="problem-icon ${p.status}">${icons[p.status] || '•'}</div>
      <div class="problem-body">
        <h4>${esc(p.title)}</h4>
        <div class="detail">${esc(p.detail)}</div>
        <div class="desc">${esc(p.description)}</div>
      </div>
    </div>
  `).join('');
}

function exportTable() {
  if (!currentData) return;
  const descLabel = showRaw ? 'Ham Log' : 'Açıklama';
  const rows = [['Zaman', 'Seviye', 'Olay', descLabel]];
  currentData.entries.forEach(e => {
    rows.push([e.time, e.level, e.event, showRaw ? e.raw : e.explanation_tr]);
  });
  downloadCSV(rows, 'log_analiz.csv');
}

function exportReport() {
  if (!currentData) return;

  const s = currentData.summary;
  const dev = currentData.device || {};
  const lines = [
    '═══════════════════════════════════════════',
    '       AirOS Log Analyzer — Rapor',
    '═══════════════════════════════════════════',
    '',
    `Kaynak       : ${currentData.source || '—'}`,
    `Oluşturulma  : ${new Date().toLocaleString('tr-TR')}`,
    '',
    '── GENEL ÖZET ──────────────────────────────',
    `Toplam Log   : ${s.total}`,
    `Bilgi (INFO) : ${s.info} (${s.info_pct}%)`,
    `Uyarı        : ${s.warning} (${s.warning_pct}%)`,
    `Hata (ERROR) : ${s.error} (${s.error_pct}%)`,
    '',
    '── CİHAZ BİLGİSİ ───────────────────────────',
    `Cihaz        : ${dev.device || '—'}`,
    `IP           : ${dev.ip || '—'}`,
    `Sürüm        : ${dev.version || '—'}`,
    `Uptime       : ${dev.uptime || '—'}`,
    '',
    '── EN ÇOK GÖRÜLEN OLAYLAR ──────────────────',
  ];

  (currentData.top_events || []).forEach(e => {
    if (e.count > 0) lines.push(`  • ${e.name}: ${e.count} kez`);
  });

  lines.push('', '── OLASI SORUNLAR ──────────────────────────');
  (currentData.problems || []).forEach(p => {
    const statusLabel = { ok: 'OK', warning: 'UYARI', error: 'HATA', info: 'BİLGİ' }[p.status] || p.status;
    lines.push(`  [${statusLabel}] ${p.title}`);
    lines.push(`         ${p.detail}`);
    lines.push(`         ${p.description}`);
    lines.push('');
  });

  lines.push('── LOG KAYITLARI ─────────────────────────────');
  (currentData.entries || []).forEach(e => {
    lines.push(`${e.time} | ${e.level} | ${e.event}`);
    lines.push(`  Açıklama: ${e.explanation_tr}`);
    lines.push(`  Ham Log : ${e.raw}`);
    lines.push('');
  });

  lines.push('═══════════════════════════════════════════');

  const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'airos_rapor.txt';
  a.click();
}

function downloadCSV(rows, filename) {
  const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
}

function openModal() {
  document.getElementById('fetch-modal').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('fetch-modal').classList.add('hidden');
}

function showToast(msg, type = 'success') {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = `toast ${type}`;
  toast.classList.remove('hidden');
  setTimeout(() => toast.classList.add('hidden'), 4000);
}

function esc(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}
