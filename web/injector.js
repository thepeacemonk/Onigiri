// Onigiri Add-on: injector.js

(function() {
    function classifyCollapseIcons() {
        const collapseElements = document.querySelectorAll('.deck-table .collapse');

        collapseElements.forEach(el => {
            // Check a flag to prevent reprocessing the same element
            if (el.dataset.onigiriClassified) return;
            el.dataset.onigiriClassified = 'true';

            // Clear any old state classes from the link itself
            el.classList.remove('state-open', 'state-closed');

            // Add the correct class directly to the link based on its text content
            if (el.textContent.includes('-')) {
                el.classList.add('state-open');
            } else {
                el.classList.add('state-closed');
            }
            // The CSS now handles hiding the text, but this is a good fallback
            el.textContent = '';
        });
    }

    // --- Main Logic ---
    document.addEventListener('DOMContentLoaded', () => {
        // --- Sidebar Resize Logic ---
        const handle = document.querySelector('.resize-handle');
        const sidebar = document.querySelector('.sidebar-left');
        if (handle && sidebar) {
            let isResizing = false;
            handle.addEventListener('mousedown', () => { isResizing = true; document.body.style.userSelect = 'none'; document.body.style.cursor = 'col-resize'; });
            document.addEventListener('mousemove', (e) => {
                if (!isResizing) return;
                let newWidth = e.clientX;
                if (newWidth < 200) newWidth = 200;
                if (newWidth > 500) newWidth = 500;
                sidebar.style.width = `${newWidth}px`;
            });
            document.addEventListener('mouseup', () => {
                if (isResizing) {
                    isResizing = false;
                    document.body.style.removeProperty('user-select'); document.body.style.removeProperty('cursor');
                    const finalWidth = parseInt(sidebar.style.width, 10);
                    if (typeof pycmd === 'function') { pycmd(`saveSidebarWidth:${finalWidth}`); }
                }
            });
        }

        // --- Collapse Icon Logic ---
        // Run once on load
        classifyCollapseIcons();

        // Run whenever the deck list changes
        const deckList = document.getElementById('deck-list-container');
        if (deckList) {
            const observer = new MutationObserver(() => { classifyCollapseIcons(); });
            observer.observe(deckList, { childList: true, subtree: true });
        }
    });
})();
