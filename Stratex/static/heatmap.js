/* TASK-IG2-WEB-04 — sector heatmap tiles for the Stratex dashboard
   (OpenTerminal pattern: one-glance sector performance from free quotes).

   Self-contained module: fetches /api/v1/market/sector-heatmap (Stooq free
   daily quotes, cached server-side for 60s), renders tiles into
   #sector-heatmap-grid, refreshes every 60s. A sector the backend could
   not price is rendered as a neutral "unavailable" tile — this module
   never invents a number. Plain script, no dependencies, loaded after
   app.js; it does not touch app.js state. */
(function () {
  'use strict';

  var REFRESH_MS = 60000;
  var CAP_PCT = 3; // |change| at which a tile reaches full colour intensity

  function tileColour(change) {
    if (change === null || change === undefined || Number.isNaN(change)) {
      return { background: 'var(--surface-soft)', border: 'var(--line)' };
    }
    var intensity = Math.min(Math.abs(change) / CAP_PCT, 1) * 0.32 + 0.06;
    if (change > 0) {
      return { background: 'rgba(180, 244, 107,' + intensity.toFixed(3) + ')', border: 'rgba(180, 244, 107,.35)' };
    }
    if (change < 0) {
      return { background: 'rgba(255, 124, 134,' + intensity.toFixed(3) + ')', border: 'rgba(255, 124, 134,.35)' };
    }
    return { background: 'var(--surface-soft)', border: 'var(--line)' };
  }

  function formatChange(change) {
    if (change === null || change === undefined) return 'unavailable';
    return (change > 0 ? '+' : '') + change.toFixed(2) + '%';
  }

  function render(payload) {
    var host = document.getElementById('sector-heatmap-grid');
    var meta = document.getElementById('sector-heatmap-meta');
    if (!host) return;
    if (!payload || !Array.isArray(payload.sectors)) {
      host.innerHTML = '<div class="section-state">Sector heatmap unavailable.</div>';
      return;
    }
    host.innerHTML = payload.sectors.map(function (sector) {
      var colour = tileColour(sector.change_pct);
      var members = (sector.members || [])
        .map(function (m) {
          return m.symbol + ' ' + (m.change_pct === null ? '—' : (m.change_pct > 0 ? '+' : '') + m.change_pct.toFixed(2) + '%');
        })
        .join(' · ');
      return (
        '<article class="heatmap-tile" style="background:' + colour.background + ';border-color:' + colour.border + '">' +
        '<span class="heatmap-sector">' + sector.sector + '</span>' +
        '<strong class="heatmap-change">' + formatChange(sector.change_pct) + '</strong>' +
        '<span class="heatmap-members">' + members + '</span>' +
        '<span class="heatmap-count">' + sector.members_available + '/' + sector.members_total + ' priced</span>' +
        '</article>'
      );
    }).join('');
    if (meta) {
      var when = payload.as_of ? new Date(payload.as_of) : null;
      meta.textContent =
        'Source: ' + (payload.source || 'free quotes') +
        (when && !Number.isNaN(when.getTime()) ? ' · as of ' + when.toUTCString().slice(17, 25) + ' UTC' : '');
    }
  }

  function load() {
    fetch('/api/v1/market/sector-heatmap', { headers: { Accept: 'application/json' } })
      .then(function (response) {
        if (!response.ok) throw new Error('heatmap HTTP ' + response.status);
        return response.json();
      })
      .then(render)
      .catch(function () {
        render(null);
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }
  setInterval(load, REFRESH_MS);
})();
