window.OnigiriProfileModal = (function () {
    function addonBase() {
        const pkg = (window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.addonPackage) || "1011095603";
        return `/_addons/${pkg}`;
    }

    function ensureLink(id, href) {
        if (document.getElementById(id)) return;
        const link = document.createElement("link");
        link.id = id;
        link.rel = "stylesheet";
        link.href = href;
        document.head.appendChild(link);
    }

    function ensureScript(id, src, callback) {
        const existing = document.getElementById(id);
        if (existing) {
            if (callback) callback();
            return;
        }
        const script = document.createElement("script");
        script.id = id;
        script.src = src;
        script.onload = () => {
            if (callback) callback();
        };
        document.head.appendChild(script);
    }

    function close() {
        const backdrop = document.getElementById("onigiri-profile-backdrop");
        if (backdrop) backdrop.remove();
    }

    function ensureStyles() {
        if (document.getElementById("onigiri-profile-modal-styles")) return;
        const style = document.createElement("style");
        style.id = "onigiri-profile-modal-styles";
        style.textContent = `
            #onigiri-profile-backdrop {
                position: fixed;
                inset: 0;
                z-index: 200000;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 26px;
                box-sizing: border-box;
                background: rgba(0, 0, 0, 0.48);
            }
            .onigiri-profile-modal {
                position: relative;
                width: min(720px, 94vw);
                height: min(760px, 90vh);
                display: flex;
                flex-direction: column;
                border: 1px solid var(--border, rgba(128, 128, 128, 0.22));
                border-radius: 14px;
                background: var(--canvas-overlay, var(--canvas, #1f1f1f));
                color: var(--fg, #e8e8e8);
                box-shadow: 0 24px 70px rgba(0, 0, 0, 0.42);
                overflow: hidden;
            }
            .onigiri-profile-modal-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                padding: 14px 18px;
                flex-shrink: 0;
                border-bottom: 1px solid var(--border, rgba(128, 128, 128, 0.18));
            }
            .onigiri-profile-modal-title {
                font-size: 15px;
                font-weight: 650;
            }
            .onigiri-profile-modal-close {
                width: 28px;
                height: 28px;
                min-width: 28px;
                padding: 0;
                border: 1px solid transparent;
                border-radius: 7px;
                background: transparent;
                color: var(--fg-subtle, #888);
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .onigiri-profile-modal-close:hover {
                background: var(--highlight-bg, rgba(128, 128, 128, 0.14));
                color: var(--fg, #e8e8e8);
            }
            .onigiri-profile-modal-close svg {
                width: 15px;
                height: 15px;
                pointer-events: none;
            }
            .onigiri-profile-modal-body {
                flex: 1;
                min-height: 0;
                overflow: auto;
                background: var(--profile-page-bg, transparent);
            }
            .onigiri-profile-modal .onigiri-profile-page {
                max-width: none;
                padding: 16px 18px 24px;
            }
            .onigiri-profile-modal .profile-header-banner {
                height: 150px;
                border-radius: 16px;
            }
            .onigiri-profile-modal main {
                box-shadow: none;
                border: 1px solid var(--border, rgba(128, 128, 128, 0.18));
                border-radius: 12px;
            }
        `;
        document.head.appendChild(style);
    }

    function renderHeatmap(payload) {
        const target = document.getElementById("onigiri-profile-heatmap-container");
        if (!target || !window.OnigiriHeatmap) return;
        window.OnigiriHeatmap.render(
            "onigiri-profile-heatmap-container",
            payload.heatmapData || {},
            payload.heatmapConfig || {}
        );
    }

    function open(payload) {
        const base = addonBase();
        ensureStyles();
        ensureLink("onigiri-profile-modal-css", `${base}/web/profile.css`);
        ensureLink("onigiri-profile-modal-heatmap-css", `${base}/web/heatmap.css`);
        close();

        const backdrop = document.createElement("div");
        backdrop.id = "onigiri-profile-backdrop";
        backdrop.addEventListener("click", close);

        const modal = document.createElement("div");
        modal.className = "onigiri-profile-modal";
        modal.addEventListener("click", event => event.stopPropagation());

        const header = document.createElement("div");
        header.className = "onigiri-profile-modal-header";
        const title = document.createElement("div");
        title.className = "onigiri-profile-modal-title";
        title.textContent = "Onigiri Profile";
        const closeBtn = document.createElement("button");
        closeBtn.className = "onigiri-profile-modal-close";
        closeBtn.type = "button";
        closeBtn.setAttribute("aria-label", "Close");
        closeBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>';
        closeBtn.addEventListener("click", close);
        header.appendChild(title);
        header.appendChild(closeBtn);

        const body = document.createElement("div");
        body.className = "onigiri-profile-modal-body";
        body.innerHTML = payload.html || "";

        modal.appendChild(header);
        modal.appendChild(body);
        backdrop.appendChild(modal);
        document.body.appendChild(backdrop);

        if (window.OnigiriProfilePage && typeof window.OnigiriProfilePage.init === "function") {
            window.OnigiriProfilePage.init(body);
        }
        ensureScript("onigiri-profile-modal-heatmap-js", `${base}/web/heatmap.js`, () => renderHeatmap(payload));
        renderHeatmap(payload);
    }

    document.addEventListener("keydown", event => {
        if (event.key === "Escape" && document.getElementById("onigiri-profile-backdrop")) {
            close();
        }
    });

    return { open, close };
})();
