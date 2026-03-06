/**
 * Observium Portal - Device Detail JS
 * Handles: period selector, graph modal, alert tab badge
 */
document.addEventListener('DOMContentLoaded', function () {

    // ── 1. PERIOD SELECTOR (Graphs tab) ──────────────────────────────
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('#obs-period-selector button[data-period]');
        if (!btn) return;

        var period = btn.dataset.period;

        // Update active button
        document.querySelectorAll('#obs-period-selector button').forEach(function (b) {
            b.classList.toggle('active', b === btn);
        });

        // Reload every graph image inside #tab-graphs
        document.querySelectorAll('#tab-graphs .obs-graph-img').forEach(function (img) {
            var graphType = img.getAttribute('data-graph');
            var deviceId  = img.getAttribute('data-device');
            if (!graphType || !deviceId) return;

            // Remove stale error message
            var naMsg = img.parentElement.querySelector('.obs-na-msg');
            if (naMsg) naMsg.remove();
            img.style.display = '';

            // Show spinner
            img.style.opacity = '0';
            var existing = img.parentElement.querySelector('.obs-graph-spinner');
            if (!existing) {
                var sp = document.createElement('div');
                sp.className = 'obs-graph-spinner text-muted small';
                sp.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading graph...';
                img.parentElement.insertBefore(sp, img);
            }

            img.src = '/my/observium/' + deviceId + '/graph/' + graphType + '?period=' + period;
        });
    });

    // ── 2. GRAPH IMAGE HANDLERS (show/hide spinner) ───────────────────
    function attachImgHandlers(img) {
        img.addEventListener('load', function () {
            img.style.opacity = '1';
            var sp = img.parentElement.querySelector('.obs-graph-spinner');
            if (sp) sp.remove();
        });
        img.addEventListener('error', function () {
            var sp = img.parentElement.querySelector('.obs-graph-spinner');
            if (sp) sp.remove();
            img.style.display = 'none';
            if (!img.parentElement.querySelector('.obs-na-msg')) {
                var msg = document.createElement('span');
                msg.className = 'text-muted small obs-na-msg';
                msg.innerHTML = '<i class="fa fa-ban me-1"></i>Not available';
                img.parentElement.appendChild(msg);
            }
        });
    }
    document.querySelectorAll('.obs-graph-img').forEach(attachImgHandlers);

    // ── 3. GRAPH MODAL (port graphs) ─────────────────────────────────
    var _triggerData = null;

    // Capture trigger data on click BEFORE Bootstrap fires show.bs.modal
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-bs-target="#obsGraphModal"]');
        if (!btn) return;
        _triggerData = {
            src:    btn.getAttribute('data-graph-src'),
            title:  btn.getAttribute('data-graph-title') || 'Graph',
            portId: btn.getAttribute('data-port-id'),
            devId:  btn.getAttribute('data-device-id'),
        };
    }, true); // useCapture=true → fires before Bootstrap

    var graphModal = document.getElementById('obsGraphModal');
    if (graphModal) {

        graphModal.addEventListener('show.bs.modal', function () {
            if (!_triggerData) return;

            var portId = _triggerData.portId;
            var devId  = _triggerData.devId;
            var src    = _triggerData.src;
            var title  = _triggerData.title;

            document.getElementById('obsGraphModalTitle').textContent = title;

            var body      = document.getElementById('obsGraphModalBody');
            var periodBar = document.getElementById('obs-modal-period');
            var isPort    = !!portId;

            periodBar.classList.toggle('d-none', !isPort);
            if (isPort) {
                periodBar.querySelectorAll('button').forEach(function (b) {
                    b.classList.toggle('active', b.dataset.period === '-1d');
                });
            }

            function loadGraph(period) {
                body.innerHTML = '<div class="obs-graph-spinner"><span class="spinner-border me-2"></span>Loading graph...</div>';
                var imgSrc = isPort
                    ? '/my/observium/' + devId + '/port/' + portId + '/graph/port_bits?period=' + period
                    : src;
                var img = new Image();
                img.className = 'img-fluid';
                img.style.maxWidth = '100%';
                img.onload = function () {
                    body.innerHTML = '';
                    body.appendChild(img);
                };
                img.onerror = function () {
                    body.innerHTML = '<span class="text-muted">Graph not available</span>';
                };
                img.src = imgSrc;
            }

            loadGraph(isPort ? '-1d' : (src || ''));

            periodBar.onclick = isPort ? function (ev) {
                var b = ev.target.closest('button[data-period]');
                if (!b) return;
                periodBar.querySelectorAll('button').forEach(function (x) {
                    x.classList.toggle('active', x === b);
                });
                loadGraph(b.dataset.period);
            } : null;
        });

        graphModal.addEventListener('hidden.bs.modal', function () {
            document.getElementById('obsGraphModalBody').innerHTML = '';
            document.getElementById('obs-modal-period').onclick = null;
            _triggerData = null;
        });
    }

    // ── 4. ALERT BADGE → open alerts tab ─────────────────────────────
    document.querySelectorAll('.obs-alert-badge[data-tab]').forEach(function (badge) {
        badge.addEventListener('click', function () {
            var t = document.querySelector('[data-bs-target="#' + badge.dataset.tab + '"]');
            if (t && window.bootstrap) bootstrap.Tab.getOrCreateInstance(t).show();
        });
    });

});