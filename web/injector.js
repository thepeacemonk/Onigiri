// Onigiri Add-on: injector.js (Clean Version)

(function() {
    function classifyCollapseIcons() {
        const collapseElements = document.querySelectorAll('.deck-table .collapse');

        collapseElements.forEach(el => {
            if (el.dataset.onigiriClassified) return;
            el.dataset.onigiriClassified = 'true';
            el.classList.remove('state-open', 'state-closed');

            if (el.textContent.includes('-')) {
                el.classList.add('state-open');
            } else {
                el.classList.add('state-closed');
            }
            el.textContent = '';
        });
    }

    function enhanceClickableAreas() {
        // --- 1. Fix Deck List Rows ---
        document.querySelectorAll('tr.deck').forEach(row => {
            if (row.dataset.onigiriClickable) return;
            row.dataset.onigiriClickable = 'true';

            const mainLink = row.querySelector('a.deck');
            const clickableCell = row.querySelector('td.decktd');

            if (mainLink && clickableCell) {
                clickableCell.style.cursor = 'pointer';
                clickableCell.addEventListener('click', (evt) => {
                    if (evt.target.closest('a.collapse')) {
                        return;
                    }
                    mainLink.click();
                });
            }
        });

        // --- 2. Fix Main Action Buttons ---
        document.querySelectorAll('.sidebar-left .menu-item, .sidebar-left .add-button-dashed')
            .forEach(item => {
                item.style.cursor = 'pointer';
            });
    }


    // --- Main Logic ---
    document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.querySelector('.sidebar-left.skeleton-loading');
    if (sidebar) {
        setTimeout(() => sidebar.classList.remove('skeleton-loading'), 150);
    }

    // --- Sidebar Toggle Logic ---
    const toggleBtn = document.querySelector('.sidebar-toggle-btn');
    const sidebarElForToggle = document.querySelector('.sidebar-left');

    if (toggleBtn && sidebarElForToggle) {
        toggleBtn.addEventListener('click', () => {
            // Toggle the 'sidebar-collapsed' class on the sidebar
            sidebarElForToggle.classList.toggle('sidebar-collapsed');

            // Check the new state and send it to Python to save it
            const isCollapsed = sidebarElForToggle.classList.contains('sidebar-collapsed');
            if (typeof pycmd === 'function') {
                pycmd(`saveSidebarState:${isCollapsed}`);
            }
        });
    }

    // --- Resize Handle Logic ---
    const handle = document.querySelector('.resize-handle');
    const sidebarEl = document.querySelector('.sidebar-left');
    if (handle && sidebarEl) {
        const indicator = document.createElement('div');
        indicator.className = 'resize-handle-indicator';
        handle.appendChild(indicator);
        let isResizing = false;
        let startX, startWidth, animationFrameId = null, lastClientX = 0;
        const updateSidebarWidth = () => {
            const deltaX = lastClientX - startX;
            let newWidth = startWidth + deltaX;
            if (newWidth < 100) newWidth = 100;
            if (newWidth > 800) newWidth = 800;
            sidebarEl.style.width = `${newWidth}px`;
            animationFrameId = null;
        };
        handle.addEventListener('mousemove', (e) => {
            if (isResizing) return;
            const rect = handle.getBoundingClientRect();
            const y = Math.max(0, Math.min(rect.height, e.clientY - rect.top));
            handle.style.setProperty('--handle-top', `${(y / rect.height) * 100}%`);
        });
        handle.addEventListener('mouseleave', () => {
            if (!isResizing) handle.style.setProperty('--handle-top', '50%');
        });
        handle.addEventListener('mousedown', (e) => {
            isResizing = true;
            startX = e.clientX;
            lastClientX = e.clientX;
            startWidth = sidebarEl.offsetWidth;
            sidebarEl.classList.add('is-resizing');
            handle.classList.add('is-resizing');
            sidebarEl.style.willChange = 'width';
            document.body.style.userSelect = 'none';
            document.body.style.cursor = 'col-resize';
        });
        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;
            lastClientX = e.clientX;
            if (!animationFrameId) {
                animationFrameId = requestAnimationFrame(updateSidebarWidth);
            }
        });
        document.addEventListener('mouseup', () => {
            if (isResizing) {
                if (animationFrameId) {
                    cancelAnimationFrame(animationFrameId);
                    animationFrameId = null;
                }
                isResizing = false;
                sidebarEl.classList.remove('is-resizing');
                handle.classList.remove('is-resizing');
                sidebarEl.style.willChange = 'auto';
                document.body.style.removeProperty('user-select');
                document.body.style.removeProperty('cursor');
                handle.style.setProperty('--handle-top', '50%');
                const finalWidth = parseInt(sidebarEl.style.width, 10);
                if (typeof pycmd === 'function') pycmd(`saveSidebarWidth:${finalWidth}`);
            }
        });
    }
    
    classifyCollapseIcons();
    enhanceClickableAreas();

    const deckList = document.getElementById('deck-list-container');
    if (deckList) {
        const observer = new MutationObserver(() => {
                classifyCollapseIcons();
                enhanceClickableAreas();
        });
        observer.observe(deckList, { childList: true, subtree: true });
    }
});
})();