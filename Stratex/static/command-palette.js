/* TASK-IG2-WEB-05 — Ctrl-K command palette for the Stratex dashboard
   (OpenTerminal pattern: keyboard-first navigation).

   Self-contained module, no dependencies. Ctrl/Cmd-K (or the topbar
   "Jump to" button) opens a palette that jumps to a view, runs a
   dashboard action, or filters the trade-activity view to a symbol —
   without touching the mouse or the menus. It drives the dashboard
   through the same DOM controls app.js already owns (nav buttons,
   refresh button, trades search box), so there is one source of truth
   for what a command does.

   The matching logic (scoreMatch / filterCommands) is pure and is
   exported for Node tests when loaded outside a browser. */
(function () {
  'use strict';

  /* ---------- pure matching (unit-testable) ---------- */

  // Subsequence fuzzy score: every query char must appear in order.
  // Higher is better; consecutive runs and word starts score more.
  // Returns -1 when the query is not a subsequence of the text.
  function scoreMatch(query, text) {
    if (!query) return 0;
    var q = query.toLowerCase();
    var t = String(text).toLowerCase();
    var score = 0;
    var ti = 0;
    var prevMatched = false;
    for (var qi = 0; qi < q.length; qi += 1) {
      var found = -1;
      for (var j = ti; j < t.length; j += 1) {
        if (t[j] === q[qi]) { found = j; break; }
      }
      if (found === -1) return -1;
      score += 1;
      if (prevMatched && found === ti) score += 2; // consecutive run
      if (found === 0 || t[found - 1] === ' ' || t[found - 1] === '/' || t[found - 1] === '-') score += 2; // word start
      ti = found + 1;
      prevMatched = found === ti - 1;
    }
    return score - (t.length - q.length) * 0.01; // prefer tighter texts
  }

  function filterCommands(commands, query) {
    return commands
      .map(function (command) {
        var score = Math.max(
          scoreMatch(query, command.title),
          scoreMatch(query, (command.keywords || []).join(' '))
        );
        return { command: command, score: score };
      })
      .filter(function (row) { return row.score >= 0; })
      .sort(function (a, b) { return b.score - a.score; })
      .map(function (row) { return row.command; });
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { scoreMatch: scoreMatch, filterCommands: filterCommands };
    return; // Node test context: no DOM wiring.
  }

  /* ---------- command catalogue ---------- */

  function clickNav(view) {
    var button = document.querySelector('.nav-item[data-view="' + view + '"]');
    if (button) button.click();
  }

  function baseCommands() {
    var views = [
      ['overview', 'Go to Overview', 'dashboard home kpi'],
      ['portfolio', 'Go to Portfolio', 'positions book exposure'],
      ['activity', 'Go to Trade activity', 'closed trades signals history'],
      ['markets', 'Go to Markets', 'quotes scanner heatmap sectors'],
      ['health', 'Go to System health', 'engine diagnostics status'],
    ];
    var commands = views.map(function (row) {
      return {
        id: 'view-' + row[0],
        title: row[1],
        hint: 'View',
        keywords: [row[2]],
        run: function () { clickNav(row[0]); },
      };
    });
    commands.push({
      id: 'action-refresh',
      title: 'Refresh dashboard data',
      hint: 'Action',
      keywords: ['reload sync update'],
      run: function () {
        var button = document.getElementById('btn-refresh');
        if (button) button.click();
      },
    });
    if (typeof window.StratexLayoutReset === 'function') {
      commands.push({
        id: 'action-reset-layout',
        title: 'Reset dashboard layout',
        hint: 'Action',
        keywords: ['layout panels restore default'],
        run: function () { window.StratexLayoutReset(); },
      });
    }
    // Symbols currently on the Markets board become jump-to-symbol commands.
    var seen = {};
    document.querySelectorAll('#market-scanner-grid .symbol-cell').forEach(function (cell) {
      var symbol = (cell.textContent || '').trim();
      if (!symbol || seen[symbol]) return;
      seen[symbol] = true;
      commands.push({
        id: 'symbol-' + symbol,
        title: 'Find trades: ' + symbol,
        hint: 'Symbol',
        keywords: [symbol.toLowerCase()],
        run: function () {
          clickNav('activity');
          var search = document.getElementById('trades-search');
          if (search) {
            search.value = symbol;
            search.dispatchEvent(new Event('input', { bubbles: true }));
          }
        },
      });
    });
    return commands;
  }

  /* ---------- palette UI ---------- */

  var overlay = null;
  var inputEl = null;
  var listEl = null;
  var activeIndex = 0;
  var currentRows = [];

  function ensureOverlay() {
    if (overlay) return overlay;
    overlay = document.createElement('div');
    overlay.className = 'palette-overlay';
    overlay.innerHTML =
      '<div class="palette" role="dialog" aria-modal="true" aria-label="Command palette">' +
      '<input class="palette-input" type="text" placeholder="Jump to a view, action or symbol…" aria-label="Command search" autocomplete="off">' +
      '<ul class="palette-list" role="listbox"></ul>' +
      '<div class="palette-foot">↑↓ navigate · Enter run · Esc close</div>' +
      '</div>';
    document.body.appendChild(overlay);
    inputEl = overlay.querySelector('.palette-input');
    listEl = overlay.querySelector('.palette-list');
    overlay.addEventListener('mousedown', function (event) {
      if (event.target === overlay) close();
    });
    inputEl.addEventListener('input', function () { render(); });
    inputEl.addEventListener('keydown', onInputKeydown);
    return overlay;
  }

  function render() {
    currentRows = filterCommands(baseCommands(), inputEl.value.trim());
    activeIndex = Math.min(activeIndex, Math.max(currentRows.length - 1, 0));
    listEl.innerHTML = currentRows
      .map(function (command, index) {
        return (
          '<li class="palette-item' + (index === activeIndex ? ' active' : '') + '" role="option" data-index="' + index + '" aria-selected="' + (index === activeIndex) + '">' +
          '<span class="palette-item-title"></span><span class="palette-item-hint">' + command.hint + '</span></li>'
        );
      })
      .join('') || '<li class="palette-empty">No matching command</li>';
    listEl.querySelectorAll('.palette-item').forEach(function (item) {
      item.querySelector('.palette-item-title').textContent = currentRows[Number(item.dataset.index)].title;
      item.addEventListener('click', function () { runAt(Number(item.dataset.index)); });
    });
  }

  function runAt(index) {
    var command = currentRows[index];
    if (!command) return;
    close();
    command.run();
  }

  function onInputKeydown(event) {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      activeIndex = Math.min(activeIndex + 1, currentRows.length - 1);
      render();
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
      render();
    } else if (event.key === 'Enter') {
      event.preventDefault();
      runAt(activeIndex);
    } else if (event.key === 'Escape') {
      close();
    }
  }

  function open() {
    ensureOverlay();
    overlay.hidden = false;
    inputEl.value = '';
    activeIndex = 0;
    render();
    inputEl.focus();
  }

  function close() {
    if (overlay) overlay.hidden = true;
  }

  function isOpen() {
    return Boolean(overlay) && !overlay.hidden;
  }

  document.addEventListener('keydown', function (event) {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      if (isOpen()) close();
      else open();
    } else if (event.key === 'Escape' && isOpen()) {
      close();
    }
  });

  var jumpButton = document.getElementById('btn-palette');
  if (jumpButton) jumpButton.addEventListener('click', open);

  window.StratexPalette = { open: open, close: close };
})();
