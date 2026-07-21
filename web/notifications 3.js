(function () {
    if (window.OnigiriNotifications) {
        return;
    }

    const STACK_ID = "onigiri-notification-stack";
    const SHADOW_HOST_ID = "onigiri-notification-shadow-host";
    const SHADOW_STYLE_ID = "onigiri-notification-shadow-style";
    const CARD_VISIBLE_CLASS = "is-visible";
    const DEFAULT_DURATION = 5200;
    const MOCHI_ICON_IMAGE = "/_addons/1011095603/system_files/gamification_images/mochi_messenger.webp";
    const pendingQueue = [];
    let domReady = document.readyState !== "loading" && !!document.body;

    function reviewerIsolationEnabled() {
        return window.onigiriIsReviewerCardWebview === true;
    }

    function isNightMode() {
        const root = document.documentElement;
        const body = document.body;
        return [root, body].some((el) => el && (
            el.classList.contains("night-mode") ||
            el.classList.contains("nightMode") ||
            el.classList.contains("night_mode")
        ));
    }

    function reviewerHeaderOffset() {
        const offset = Number(window.onigiriReviewerHeaderOffsetPx);
        return Number.isFinite(offset) && offset >= 0 ? offset : 0;
    }

    function shadowCssText() {
        return `
            :host {
                --onigiri-notification-max-width: min(360px, calc(100vw - 32px));
                --onigiri-notification-bg-light: #ffffff;
                --onigiri-notification-bg-dark: #2c2c2c;
                --onigiri-notification-text-light: #2c2c2c;
                --onigiri-notification-text-dark: #ffffff;
                all: initial;
                position: fixed !important;
                inset: 0 !important;
                display: block !important;
                z-index: 2147483001 !important;
                pointer-events: none !important;
                contain: layout style paint !important;
            }
        ` + (window.onigiriNotificationCssText || "") + "\n" + (window.onigiriNotificationPositionCssText || "");
    }

    function ensureReviewerRoot() {
        let host = document.getElementById(SHADOW_HOST_ID);
        if (!host) {
            host = document.createElement("div");
            host.id = SHADOW_HOST_ID;
            document.body.appendChild(host);
        }
        host.style.cssText = [
            "all: initial !important",
            "position: fixed !important",
            "inset: 0 !important",
            "display: block !important",
            "width: auto !important",
            "height: auto !important",
            "margin: 0 !important",
            "padding: 0 !important",
            "border: 0 !important",
            "background: transparent !important",
            "z-index: 2147483001 !important",
            "pointer-events: none !important",
            "contain: layout style paint !important"
        ].join(";");
        host.classList.toggle("night-mode", isNightMode());

        const root = host.shadowRoot || host.attachShadow({ mode: "open" });
        let style = root.getElementById(SHADOW_STYLE_ID);
        if (!style) {
            style = document.createElement("style");
            style.id = SHADOW_STYLE_ID;
            root.prepend(style);
        }
        const css = shadowCssText();
        if (style.textContent !== css) {
            style.textContent = css;
        }
        return root;
    }

    function stackRoot(createIfMissing) {
        if (!reviewerIsolationEnabled()) {
            return document;
        }
        if (!createIfMissing && !document.getElementById(SHADOW_HOST_ID)) {
            return null;
        }
        return ensureReviewerRoot();
    }

    function findStack() {
        const root = stackRoot(false);
        return root && root.getElementById ? root.getElementById(STACK_ID) : null;
    }

    function syncReviewerState(stack) {
        if (!stack || !reviewerIsolationEnabled()) {
            return;
        }
        const night = isNightMode();
        stack.classList.toggle("night-mode", night);
        stack.classList.toggle("nightMode", night);
        stack.style.setProperty("--onigiri-reviewer-header-offset", reviewerHeaderOffset() + "px");
    }

    function removeReviewerHostIfEmpty() {
        if (!reviewerIsolationEnabled()) {
            return;
        }
        const host = document.getElementById(SHADOW_HOST_ID);
        if (host && host.shadowRoot && !host.shadowRoot.getElementById(STACK_ID)) {
            host.remove();
        }
    }

    function displayDuration(data) {
        const configured = Number(window.onigiriNotificationDuration);
        if (Number.isFinite(configured) && configured > 0) {
            return Math.max(1000, Math.min(30000, configured));
        }
        const payloadDuration = Number(data && data.duration);
        if (Number.isFinite(payloadDuration) && payloadDuration > 0) {
            return Math.max(1000, Math.min(30000, payloadDuration));
        }
        return DEFAULT_DURATION;
    }

    function ensureDomReady(callback) {
        if (domReady) {
            callback();
            return;
        }
        pendingQueue.push(callback);
    }

    function flushPending() {
        if (!domReady) {
            return;
        }
        while (pendingQueue.length) {
            try {
                const job = pendingQueue.shift();
                job();
            } catch (err) {
                console.error("OnigiriNotifications: pending job failed", err);
            }
        }
    }

    if (!domReady) {
        window.addEventListener("DOMContentLoaded", () => {
            domReady = true;
            flushPending();
        }, { once: true });
        window.addEventListener("load", () => {
            domReady = true;
            flushPending();
        }, { once: true });
    }

    function ensureStack() {
        const root = stackRoot(true);
        let stack = root.getElementById(STACK_ID);
        if (!stack) {
            stack = document.createElement("div");
            stack.id = STACK_ID;
            stack.className = "onigiri-notification-stack";
            if (reviewerIsolationEnabled()) {
                root.appendChild(stack);
            } else {
                document.body.appendChild(stack);
            }
        }
        syncReviewerState(stack);
        return stack;
    }

    function updateForcedTopState(stack) {
        if (!stack) {
            return;
        }
        const hasForcedTop = !!stack.querySelector('[data-force-top="true"]');
        stack.classList.toggle("is-forced-top", hasForcedTop);
    }

    function removeCard(card) {
        const root = card.getRootNode && card.getRootNode();
        const stackBeforeRemove = root && root.getElementById ? root.getElementById(STACK_ID) : findStack();
        card.classList.remove(CARD_VISIBLE_CLASS);
        const duration = Math.max(160, parseFloat(getComputedStyle(card).transitionDuration || "0") * 1000);
        window.setTimeout(() => {
            card.remove();
            const stack = stackBeforeRemove || findStack();
            if (stack && stack.children.length === 0) {
                stack.remove();
                removeReviewerHostIfEmpty();
            } else {
                updateForcedTopState(stack);
            }
        }, duration);
    }

    function renderNotification(data) {
        if (window.onigiriNotificationMode === "mini") {
            let headerBtnContainer = null;
            if (window.onigiriIsReviewerCardWebview) {
                const uiHost = document.getElementById('onigiri-reviewer-ui-host');
                if (uiHost && uiHost.shadowRoot) {
                    headerBtnContainer = uiHost.shadowRoot.querySelector('.onigiri-reviewer-header-buttons');
                }
            } else {
                headerBtnContainer = document.querySelector('.onigiri-reviewer-header-buttons');
            }
            if (headerBtnContainer) {
                const existing = headerBtnContainer.querySelector('.onigiri-mini-notification');
                if (existing) {
                    existing.remove();
                }

                const card = document.createElement("div");
                card.className = "onigiri-mini-notification";
                
                if (data.textColorLight) {
                    card.style.setProperty("--onigiri-notification-text-light", data.textColorLight);
                }
                if (data.textColorDark) {
                    card.style.setProperty("--onigiri-notification-text-dark", data.textColorDark);
                }
                if (data.fontFamily) {
                    card.style.setProperty("--notification-font", data.fontFamily);
                }

                let iconImageSrc = null;
                if (Object.prototype.hasOwnProperty.call(data, "iconImage")) {
                    iconImageSrc = data.iconImage || null;
                } else if (data.variant === "mochi" || data.id === "mochi_message") {
                    iconImageSrc = MOCHI_ICON_IMAGE;
                } else if (data.icon && (data.icon.includes("/") || data.icon.includes("."))) {
                    iconImageSrc = data.icon;
                }

                if (!data.hideIcon) {
                    const icon = document.createElement("div");
                    icon.className = "onigiri-mini-notification-icon";
                    if (iconImageSrc) {
                        const img = document.createElement("img");
                        img.src = iconImageSrc;
                        img.alt = data.iconAlt || "";
                        icon.appendChild(img);
                    } else {
                        icon.textContent = data.icon || "🍙";
                    }
                    card.appendChild(icon);
                }

                const content = document.createElement("div");
                content.className = "onigiri-mini-notification-content";
                content.textContent = data.description || data.name || "";
                card.appendChild(content);

                headerBtnContainer.appendChild(card);

                const showCard = () => {
                    card.classList.add(CARD_VISIBLE_CLASS);
                };

                requestAnimationFrame(() => requestAnimationFrame(showCard));

                const duration = displayDuration(data);
                let hideTimer = window.setTimeout(() => removeCard(card), duration);

                card.addEventListener("mouseenter", () => {
                    window.clearTimeout(hideTimer);
                });
                card.addEventListener("mouseleave", () => {
                    hideTimer = window.setTimeout(() => removeCard(card), duration);
                });
                card.addEventListener("click", () => {
                    removeCard(card);
                });
                
                return;
            }
        }

        const stack = ensureStack();
        if (data.forceTop) {
            stack.classList.add("is-forced-top");
        }
        const card = document.createElement("article");
        card.className = "onigiri-notification-card";
        if (data.forceTop) {
            card.dataset.forceTop = "true";
        }
        if (data.variant) {
            card.dataset.variant = data.variant;
        } else if (data.id === "mochi_message") {
            card.dataset.variant = "mochi";
        }
        if (data.hideIcon) {
            card.classList.add("has-no-icon");
        }
        if (data.hideTitle) {
            card.classList.add("has-no-title");
        }
        if (data.centered) {
            card.classList.add("is-centered");
        }

        if (data.textColorLight) {
            card.style.setProperty("--notification-text-light", data.textColorLight);
        }
        if (data.textColorDark) {
            card.style.setProperty("--notification-text-dark", data.textColorDark);
        }
        if (data.fontFamily) {
            card.style.setProperty("--notification-font", data.fontFamily);
        }

        const icon = document.createElement("div");
        icon.className = "onigiri-notification-icon";

        let iconImageSrc = null;
        if (Object.prototype.hasOwnProperty.call(data, "iconImage")) {
            iconImageSrc = data.iconImage || null;
        } else if (card.dataset.variant === "mochi" || data.id === "mochi_message") {
            iconImageSrc = MOCHI_ICON_IMAGE;
        } else if (data.icon && (data.icon.includes("/") || data.icon.includes("."))) {
            iconImageSrc = data.icon;
        }

        if (iconImageSrc) {
            const img = document.createElement("img");
            img.src = iconImageSrc;
            img.alt = data.iconAlt || "";
            icon.appendChild(img);
        } else {
            icon.textContent = data.icon || "🍙";
        }

        const content = document.createElement("div");
        content.className = "onigiri-notification-content";

        const title = document.createElement("p");
        title.className = "onigiri-notification-title";
        title.textContent = data.name || "Achievement unlocked";

        const description = document.createElement("p");
        description.className = "onigiri-notification-description";
        description.textContent = data.description || "";

        if (!data.hideTitle) {
            content.appendChild(title);
        }
        if (description.textContent) {
            content.appendChild(description);
        }
        if (data.rewardItems && data.rewardItems.forEach) {
            const rewards = document.createElement("div");
            rewards.className = "onigiri-notification-rewards";
            data.rewardItems.forEach((item) => {
                const reward = document.createElement("span");
                reward.className = "onigiri-notification-reward";
                if (item.iconImage) {
                    const img = document.createElement("img");
                    img.src = item.iconImage;
                    img.alt = item.iconAlt || "";
                    reward.appendChild(img);
                }
                const value = document.createElement("span");
                value.textContent = String(item.value || "");
                reward.appendChild(value);
                rewards.appendChild(reward);
            });
            content.appendChild(rewards);
        }

        if (!data.hideIcon) {
            card.appendChild(icon);
        }
        card.appendChild(content);

        stack.appendChild(card);

        const showCard = () => {
            card.classList.add(CARD_VISIBLE_CLASS);
        };

        requestAnimationFrame(() => requestAnimationFrame(showCard));

        const duration = displayDuration(data);
        let hideTimer = window.setTimeout(() => removeCard(card), duration);

        card.addEventListener("mouseenter", () => {
            window.clearTimeout(hideTimer);
        });
        card.addEventListener("mouseleave", () => {
            hideTimer = window.setTimeout(() => removeCard(card), duration);
        });
        card.addEventListener("click", () => {
            removeCard(card);
        });
    }

    const api = {
        show(payload) {
            if (!reviewerIsolationEnabled() || window.onigiriSilentNotifications) {
                return;
            }
            ensureDomReady(() => renderNotification(payload || {}));
        },
        showMany(items) {
            if (!items || !items.forEach) {
                return;
            }
            items.forEach((item) => {
                api.show(item || {});
            });
        },
        clear() {
            const stack = findStack();
            if (stack) {
                stack.remove();
                removeReviewerHostIfEmpty();
            }
        },
    };

    window.addEventListener("onigiri-reviewer-header-offset", () => {
        syncReviewerState(findStack());
    });

    window.OnigiriNotifications = api;
})();
