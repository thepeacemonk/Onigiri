(function () {
    if (window.OnigiriNotifications) {
        return;
    }

    const STACK_ID = "onigiri-notification-stack";
    const CARD_VISIBLE_CLASS = "is-visible";
    const DEFAULT_DURATION = 5200;
    const MOCHI_ICON_IMAGE = "/_addons/1011095603/system_files/gamification_images/mochi_messenger.png";
    const pendingQueue = [];
    let domReady = document.readyState !== "loading" && !!document.body;

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
        let stack = document.getElementById(STACK_ID);
        if (!stack) {
            stack = document.createElement("div");
            stack.id = STACK_ID;
            stack.className = "onigiri-notification-stack";
            document.body.appendChild(stack);
        }
        return stack;
    }

    function removeCard(card) {
        card.classList.remove(CARD_VISIBLE_CLASS);
        const duration = Math.max(160, parseFloat(getComputedStyle(card).transitionDuration || "0") * 1000);
        window.setTimeout(() => {
            card.remove();
            const stack = document.getElementById(STACK_ID);
            if (stack && stack.children.length === 0) {
                stack.remove();
            }
        }, duration);
    }

    function renderNotification(data) {
        const stack = ensureStack();
        const card = document.createElement('article');
        card.className = 'onigiri-notification-card';
        if (data.variant) {
            card.dataset.variant = data.variant;
        } else if (data.id === 'mochi_message') {
            card.dataset.variant = 'mochi';
        }

        if (data.textColorLight) {
            card.style.setProperty('--notification-text-light', data.textColorLight);
        }
        if (data.textColorDark) {
            card.style.setProperty('--notification-text-dark', data.textColorDark);
        }

        const icon = document.createElement('div');
        icon.className = 'onigiri-notification-icon';

        let iconImageSrc = null;
        if (Object.prototype.hasOwnProperty.call(data, 'iconImage')) {
            iconImageSrc = data.iconImage || null;
        } else if (card.dataset.variant === 'mochi' || data.id === 'mochi_message') {
            iconImageSrc = MOCHI_ICON_IMAGE;
        } else if (data.icon && (data.icon.includes('/') || data.icon.includes('.'))) {
            iconImageSrc = data.icon;
        }

        if (iconImageSrc) {
            const img = document.createElement('img');
            img.src = iconImageSrc;
            img.alt = data.iconAlt || '';
            icon.appendChild(img);
        } else {
            icon.textContent = data.icon || '🍙';
        }

        const content = document.createElement('div');
        content.className = 'onigiri-notification-content';

        const title = document.createElement("p");
        title.className = "onigiri-notification-title";
        title.textContent = data.name || "Achievement unlocked";

        const description = document.createElement("p");
        description.className = "onigiri-notification-description";
        description.textContent = data.description || "";

        content.appendChild(title);
        if (description.textContent) {
            content.appendChild(description);
        }

        card.appendChild(icon);
        card.appendChild(content);

        stack.appendChild(card);

        const showCard = () => {
            card.classList.add(CARD_VISIBLE_CLASS);
        };

        requestAnimationFrame(() => requestAnimationFrame(showCard));

        let hideTimer = window.setTimeout(() => removeCard(card), data.duration || DEFAULT_DURATION);

        card.addEventListener("mouseenter", () => {
            window.clearTimeout(hideTimer);
        });
        card.addEventListener("mouseleave", () => {
            hideTimer = window.setTimeout(() => removeCard(card), data.duration || DEFAULT_DURATION);
        });
        card.addEventListener("click", () => {
            removeCard(card);
        });
    }

    const api = {
        show(payload) {
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
            const stack = document.getElementById(STACK_ID);
            if (stack) {
                stack.remove();
            }
        },
    };

    window.OnigiriNotifications = api;
})();
