/* TASK-IG2-WEB-06 — persisted dashboard widget layouts for Stratex
   (OpenTerminal pattern: drag/resize widget workspace, layouts saved).

   Self-contained module, no dependencies. The dashboard's panel grids
   (.overview-grid on Overview, .health-grid on System health) become a
   widget workspace:

   - Drag a panel by its heading to reorder it within its grid.
   - Drag the handle at a panel's bottom-right corner to resize it:
     horizontal movement widens/narrows the panel across grid columns
     (span 1 or 2), vertical movement sets its minimum height.
   - The layout (order, spans, heights) is saved to localStorage and
     restored on the next visit. Nothing is sent to the server — layout
     is a per-browser preference, and the fleet stores nothing for it.
   - Reset via the command palette ("Reset dashboard layout",
     TASK-IG2-WEB-05) or window.StratexLayoutReset().

   Grid honesty: the dashboard grids are CSS grids, so "resize" means
   column span + minimum height rather than free pixel geometry — the
   panels can never overlap or leave the grid, which is the behaviour a
   data workspace wants. */
(function () {
  'use strict';

  var STORAGE_KEY = 'stratex.dashboard.layout.v1';
  var GRIDS = ['overview-grid', 'health-grid'];

  function slug(text) {
    return String(text || '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }

  function panelKey(panel) {
    var heading = panel.querySelector('.panel-heading h2');
    return slug(heading ? heading.textContent : panel.className);
  }

  function loadState() {
    try {
      var raw = window.localStorage.getItem(STORAGE_KEY);
      var parsed = raw ? JSON.parse(raw) : null;
      if (parsed && typeof parsed === 'object') {
        return {
          order: parsed.order || {},
          spans: parsed.spans || {},
          heights: parsed.heights || {},
        };
      }
    } catch (error) {
      /* storage unavailable (private mode etc.) — layout just won't persist */
    }
    return { order: {}, spans: {}, heights: {} };
  }

  function saveState(state) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (error) {
      /* non-fatal: see loadState */
    }
  }

  var state = loadState();
  var originalOrder = {}; // containerKey -> [panel elements in shipped order]

  function applyPanelGeometry(panel) {
    var key = panelKey(panel);
    var span = state.spans[key];
    panel.style.gridColumn = span ? 'span ' + span : '';
    var height = state.heights[key];
    panel.style.minHeight = height ? height + 'px' : '';
  }

  function applyOrder(grid, containerKey) {
    var wanted = state.order[containerKey];
    if (!Array.isArray(wanted) || !wanted.length) return;
    var byKey = {};
    Array.prototype.forEach.call(grid.children, function (panel) {
      byKey[panelKey(panel)] = panel;
    });
    wanted.forEach(function (key) {
      if (byKey[key]) grid.appendChild(byKey[key]);
    });
  }

  function recordOrder(grid, containerKey) {
    state.order[containerKey] = Array.prototype.map.call(grid.children, function (panel) {
      return panelKey(panel);
    });
    saveState(state);
  }

  /* ---------- drag to reorder ---------- */

  function enableDrag(grid, containerKey, panel) {
    var heading = panel.querySelector('.panel-heading');
    if (!heading) return;
    heading.classList.add('layout-drag-handle');
    heading.addEventListener('pointerdown', function (event) {
      if (event.target.closest('button, a, input, select, textarea')) return;
      event.preventDefault();
      panel.classList.add('layout-dragging');
      var startY = event.clientY;
      var moved = false;

      function onMove(moveEvent) {
        var dy = moveEvent.clientY - startY;
        if (Math.abs(dy) > 4) moved = true;
        if (!moved) return;
        var siblings = Array.prototype.filter.call(grid.children, function (el) {
          return el !== panel;
        });
        for (var i = 0; i < siblings.length; i += 1) {
          var rect = siblings[i].getBoundingClientRect();
          if (moveEvent.clientY < rect.top + rect.height / 2) {
            if (siblings[i] !== panel.nextElementSibling) grid.insertBefore(panel, siblings[i]);
            return;
          }
        }
        if (grid.lastElementChild !== panel) grid.appendChild(panel);
      }

      function onUp() {
        document.removeEventListener('pointermove', onMove);
        document.removeEventListener('pointerup', onUp);
        panel.classList.remove('layout-dragging');
        if (moved) recordOrder(grid, containerKey);
      }

      document.addEventListener('pointermove', onMove);
      document.addEventListener('pointerup', onUp);
    });
  }

  /* ---------- resize (span + min-height) ---------- */

  function enableResize(grid, panel) {
    var handle = document.createElement('span');
    handle.className = 'layout-resize-handle';
    handle.setAttribute('aria-hidden', 'true');
    handle.title = 'Drag to resize panel';
    panel.appendChild(handle);
    handle.addEventListener('pointerdown', function (event) {
      event.preventDefault();
      event.stopPropagation();
      var startX = event.clientX;
      var startY = event.clientY;
      var startHeight = panel.getBoundingClientRect().height;
      var gridWidth = grid.getBoundingClientRect().width;
      var key = panelKey(panel);

      function onMove(moveEvent) {
        var dx = moveEvent.clientX - startX;
        // One column is roughly half the two-column grid; crossing half a
        // column of drag flips the span.
        var span = state.spans[key] || 1;
        if (dx > gridWidth / 4) span = 2;
        if (dx < -gridWidth / 4) span = 1;
        state.spans[key] = span;
        panel.style.gridColumn = 'span ' + span;
        var height = Math.max(140, Math.round(startHeight + (moveEvent.clientY - startY)));
        state.heights[key] = height;
        panel.style.minHeight = height + 'px';
      }

      function onUp() {
        document.removeEventListener('pointermove', onMove);
        document.removeEventListener('pointerup', onUp);
        saveState(state);
      }

      document.addEventListener('pointermove', onMove);
      document.addEventListener('pointerup', onUp);
    });
  }

  /* ---------- reset ---------- */

  function resetLayout() {
    state = { order: {}, spans: {}, heights: {} };
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      /* non-fatal */
    }
    GRIDS.forEach(function (containerKey) {
      var grid = document.querySelector('.' + containerKey);
      if (!grid) return;
      (originalOrder[containerKey] || []).forEach(function (panel) {
        grid.appendChild(panel);
        panel.style.gridColumn = '';
        panel.style.minHeight = '';
      });
    });
  }
  window.StratexLayoutReset = resetLayout;

  /* ---------- init ---------- */

  function init() {
    GRIDS.forEach(function (containerKey) {
      var grid = document.querySelector('.' + containerKey);
      if (!grid) return;
      originalOrder[containerKey] = Array.prototype.slice.call(grid.children);
      applyOrder(grid, containerKey);
      Array.prototype.forEach.call(grid.children, function (panel) {
        panel.classList.add('layout-panel');
        applyPanelGeometry(panel);
        enableDrag(grid, containerKey, panel);
        enableResize(grid, panel);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
