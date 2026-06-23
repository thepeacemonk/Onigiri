/* Onigiri "party mode" — special-day visuals on the deck browser.
 *
 * Reads window.ONIGIRI_PARTY_MODE (injected by inject_menu_files only on a
 * special day) and layers effects on top of the rendered page:
 *   - a confetti burst on open, then a gentle, capped continuous drift
 *   - a festive emoji badge on today's heatmap cell
 *   - a body class (.onigiri-party-mode) that drives the CSS glow
 *
 * It never touches the heatmap's own rendering; it only observes for the
 * already-existing `.heatmap-day-cell.today` element and decorates it.
 */
(function () {
    if (window.OnigiriParty) {
        return;
    }

    var payload = window.ONIGIRI_PARTY_MODE;
    if (!payload) {
        return;
    }

    var PALETTE = [
        "#ff9800", "#ff5722", "#e91e63", "#9c27b0", "#673ab7", "#3f51b5",
        "#2196f3", "#03a9f4", "#00bcd4", "#009688", "#4caf50", "#8bc34a",
        "#cddc39", "#ffeb3b", "#ffc107", "#ff5fa2", "#ffd700"
    ];
    function randColor() { return PALETTE[Math.floor(Math.random() * PALETTE.length)]; }
    function rand(min, max) { return Math.random() * (max - min) + min; }

    var api = { started: false };
    window.OnigiriParty = api;

    function ready(fn) {
        if (document.readyState !== "loading" && document.body) {
            fn();
        } else {
            document.addEventListener("DOMContentLoaded", fn, { once: true });
        }
    }

    // --- Confetti -------------------------------------------------------------
    var container = null;
    var driftTimer = null;

    function ensureContainer() {
        if (container && document.body.contains(container)) {
            return container;
        }
        container = document.createElement("div");
        container.className = "onigiri-party-confetti";
        document.body.appendChild(container);
        return container;
    }

    function spawnPiece(fast) {
        var c = ensureContainer();
        var piece = document.createElement("div");
        piece.className = "onigiri-party-piece";
        var size = rand(6, 12);
        piece.style.width = size + "px";
        piece.style.height = size + "px";
        piece.style.left = rand(0, 100) + "%";
        piece.style.background = randColor();
        if (Math.random() < 0.5) {
            piece.style.borderRadius = "50%";
        }
        piece.style.animationDuration = (fast ? rand(1.4, 2.6) : rand(3.5, 6.5)) + "s";
        piece.style.setProperty("--drift", rand(-60, 60).toFixed(0) + "px");
        piece.addEventListener("animationend", function () { piece.remove(); });
        c.appendChild(piece);
    }

    function burst(n) {
        for (var i = 0; i < n; i++) {
            window.setTimeout(function () { spawnPiece(true); }, i * 25);
        }
    }

    function startDrift() {
        if (driftTimer) {
            return;
        }
        driftTimer = window.setInterval(function () {
            if (document.hidden) {
                return;
            }
            // Keep it gentle: cap the number of live pieces.
            var live = container ? container.childElementCount : 0;
            if (live < 24) {
                spawnPiece(false);
            }
        }, 450);
    }

    function stopConfetti() {
        if (driftTimer) {
            window.clearInterval(driftTimer);
            driftTimer = null;
        }
        if (container) {
            container.remove();
            container = null;
        }
    }

    // --- Heatmap today-cell emoji --------------------------------------------
    function stampHeatmap() {
        var cell = document.querySelector(".heatmap-day-cell.today");
        if (!cell) {
            return false;
        }
        if (cell.querySelector(".onigiri-party-emoji")) {
            return true;
        }
        var span = document.createElement("span");
        span.className = "onigiri-party-emoji";
        span.textContent = payload.emoji || "🎉";
        cell.appendChild(span);
        return true;
    }

    function watchHeatmap() {
        if (stampHeatmap()) {
            return;
        }
        // The heatmap renders asynchronously (OnigiriHeatmap.autoRender), so
        // wait for today's cell to appear before decorating it.
        var attempts = 0;
        var obs = new MutationObserver(function () {
            if (stampHeatmap() || attempts++ > 60) {
                obs.disconnect();
            }
        });
        obs.observe(document.body, { childList: true, subtree: true });
        window.setTimeout(function () { obs.disconnect(); }, 15000);
    }

    // --- Boot -----------------------------------------------------------------
    ready(function () {
        if (api.started) {
            return;
        }
        api.started = true;
        document.body.classList.add("onigiri-party-mode");

        if (payload.confetti) {
            burst(40);
            startDrift();
        }
        if (payload.heatmap_effect) {
            watchHeatmap();
        }

        window.addEventListener("pagehide", stopConfetti, { once: true });
    });
})();
