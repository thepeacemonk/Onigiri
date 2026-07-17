/*
    Onigiri Modal Factory

    Shared anti-flicker scaffolding for deck-browser-embedded DOM-overlay
    dialogs (the same architecture as rename_dialog.js / create_deck_dialog.js
    / move_to_dialog.js / add_subdeck_dialog.js): warmup pre-render at script
    load, is-preparing + double-rAF reveal, cleanup-stack, Escape/backdrop-click
    to close, and the onigiri_ui_open/onigiri_ui_close pycmd bridge that tells
    the deck browser to defer its own refresh while a dialog is open.

    Each of those four existing dialogs duplicates this ~150 lines verbatim.
    This factory exists so the two NEW dialogs (Main Menu Settings, Widget
    Layout Editor) don't duplicate it a fifth and sixth time. It intentionally
    does NOT touch the four existing dialogs.
*/

window.OnigiriModal = window.OnigiriModal || {};

(function (exports) {
    "use strict";

    function create(config) {
        config = config || {};
        var id = config.id || ("modal-" + Math.random().toString(36).slice(2));
        var backdropId = "onigiri-" + id + "-backdrop";
        var styleId = "onigiri-" + id + "-style";
        var warmupId = "onigiri-" + id + "-warmup";
        // Dialogs that stack ON TOP of another already-open Onigiri dialog
        // (currently: the Widget Layout Editor, opened from inside the Main
        // Menu dialog) must NOT participate in the page-level UI-state bridge —
        // the outer dialog already owns onigiri_ui_open/close and the
        // dialog-focus override state; a nested dialog tearing that down on
        // its own close would break the outer dialog it's stacked on.
        var ownsGlobalUiState = config.ownsGlobalUiState !== false;

        var cleanupFns = [];
        var currentBackdrop = null;

        function addCleanup(fn) {
            cleanupFns.push(fn);
        }

        function runCleanup() {
            while (cleanupFns.length) {
                var fn = cleanupFns.pop();
                try { fn(); } catch (_) {}
            }
        }

        function ensureStyles() {
            if (!config.styleCss) return; // dialogs may ship a <link> stylesheet instead
            if (document.getElementById(styleId)) return;
            var style = document.createElement("style");
            style.id = styleId;
            style.textContent = config.styleCss;
            document.head.appendChild(style);
        }

        function warmDialogSurface() {
            if (typeof config.buildWarmup !== "function") return;
            if (document.getElementById(warmupId)) return;
            var warmup = config.buildWarmup();
            if (!warmup) return;
            warmup.id = warmupId;
            warmup.setAttribute("aria-hidden", "true");
            warmup.style.position = "fixed";
            warmup.style.left = "-10000px";
            warmup.style.top = "-10000px";
            warmup.style.visibility = "hidden";
            warmup.style.pointerEvents = "none";
            warmup.style.contain = "layout paint style";
            warmup.style.overflow = "hidden";
            (document.body || document.documentElement).appendChild(warmup);
            warmup.getBoundingClientRect();
        }

        function revealWhenStable(backdrop, focusTarget) {
            if (!backdrop) return;
            backdrop.getBoundingClientRect();
            requestAnimationFrame(function () {
                requestAnimationFrame(function () {
                    backdrop.classList.remove("is-preparing");
                    if (!focusTarget) return;
                    try {
                        focusTarget.focus({ preventScroll: true });
                    } catch (_) {
                        focusTarget.focus();
                    }
                    if (typeof focusTarget.select === "function") focusTarget.select();
                });
            });
        }

        function close(skipUiClose) {
            var backdrop = document.getElementById(backdropId);
            runCleanup();
            if (backdrop) backdrop.remove();
            currentBackdrop = null;

            if (ownsGlobalUiState) {
                if (window.OnigiriEngine && typeof OnigiriEngine.clearDialogFocus === "function") {
                    OnigiriEngine.clearDialogFocus();
                } else {
                    document.querySelectorAll("tr.deck.ctx-row-active").forEach(function (row) {
                        row.classList.remove("ctx-row-active");
                    });
                    document.body.classList.remove("dialog-focus");
                }
            }

            if (typeof config.onClose === "function") {
                try { config.onClose(skipUiClose); } catch (_) {}
            }

            if (ownsGlobalUiState && !skipUiClose && backdrop && typeof pycmd === "function") {
                pycmd("onigiri_ui_close");
            }
        }

        function open(data) {
            if (typeof config.onBeforeOpen === "function") {
                try { config.onBeforeOpen(data); } catch (_) {}
            }
            close(true);
            ensureStyles();

            if (ownsGlobalUiState) {
                if (window.OnigiriEngine && typeof OnigiriEngine._beginOverrideState === "function") {
                    OnigiriEngine._beginOverrideState("dialog-focus");
                } else {
                    document.body.classList.add("dialog-focus");
                }
            }

            var result = config.buildBackdrop(data || {}) || {};
            var backdrop = result.backdrop;
            var focusTarget = result.focusTarget;
            if (!backdrop) return;
            if (!backdrop.id) backdrop.id = backdropId;
            currentBackdrop = backdrop;

            backdrop.addEventListener("pointerdown", function (evt) {
                if (evt.target === backdrop) close(false);
            });

            var keyHandler = function (evt) {
                if (evt.key === "Escape") {
                    evt.preventDefault();
                    evt.stopPropagation();
                    close(false);
                }
            };
            document.addEventListener("keydown", keyHandler, true);
            addCleanup(function () {
                document.removeEventListener("keydown", keyHandler, true);
            });

            revealWhenStable(backdrop, focusTarget);
            if (ownsGlobalUiState && typeof pycmd === "function") pycmd("onigiri_ui_open");
        }

        ensureStyles();
        warmDialogSurface();

        return {
            open: open,
            close: close,
            addCleanup: addCleanup,
            isOpen: function () { return !!currentBackdrop; }
        };
    }

    exports.create = create;
})(window.OnigiriModal);
