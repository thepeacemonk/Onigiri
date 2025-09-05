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
        // --- Skeleton Loader Reveal ---
        const sidebar = document.querySelector('.sidebar-left.skeleton-loading');
        if (sidebar) {
            // Use a short timeout to ensure styles are applied before removing the class
            setTimeout(() => {
                sidebar.classList.remove('skeleton-loading');
            }, 150); // A small delay like 150ms feels good
        }

        // --- Sidebar Resize Logic ---
        const handle = document.querySelector('.resize-handle');
        const sidebarEl = document.querySelector('.sidebar-left');
        if (handle && sidebarEl) {
            // Dynamically create and append the indicator element for styling
            const indicator = document.createElement('div');
            indicator.className = 'resize-handle-indicator';
            handle.appendChild(indicator);

            let isResizing = false;

            // Make the indicator follow the cursor precisely within the handle area
            handle.addEventListener('mousemove', (e) => {
                const rect = handle.getBoundingClientRect();
                // Calculate vertical position, ensuring it stays within bounds (0% to 100%)
                const y = Math.max(0, Math.min(rect.height, e.clientY - rect.top));
                const yPercentage = (y / rect.height) * 100;
                handle.style.setProperty('--handle-top', `${yPercentage}%`);
            });

            // Animate the indicator back to center when the mouse leaves
            handle.addEventListener('mouseleave', () => {
                if (!isResizing) {
                    handle.style.setProperty('--handle-top', '50%');
                }
            });

            // Start the resizing process
            handle.addEventListener('mousedown', () => {
                isResizing = true;
                sidebarEl.classList.add('is-resizing'); // Add class to sidebar to disable transition
                handle.classList.add('is-resizing'); // Add class for active styling
                document.body.style.userSelect = 'none';
                document.body.style.cursor = 'col-resize';
            });

            // Handle the actual sidebar resizing
            document.addEventListener('mousemove', (e) => {
                if (!isResizing) return;
                let newWidth = e.clientX;
                // Enforce min and max widths
                if (newWidth < 200) newWidth = 200;
                if (newWidth > 500) newWidth = 500;
                sidebarEl.style.width = `${newWidth}px`;
            });

            // Stop resizing and reset everything
            document.addEventListener('mouseup', () => {
                if (isResizing) {
                    isResizing = false;
                    sidebarEl.classList.remove('is-resizing'); // Remove class to re-enable transition
                    handle.classList.remove('is-resizing'); // Remove active class
                    document.body.style.removeProperty('user-select');
                    document.body.style.removeProperty('cursor');
                    
                    // Trigger the animation back to center
                    handle.style.setProperty('--handle-top', '50%');

                    const finalWidth = parseInt(sidebarEl.style.width, 10);
                    if (typeof pycmd === 'function') {
                        pycmd(`saveSidebarWidth:${finalWidth}`);
                    }
                }
            });
        }


        // --- Collapse Icon Logic ---
        // Run once on load
        classifyCollapseIcons();

        // Run whenever the deck list changes
        const deckList = document.getElementById('deck-list-container');
        if (deckList) {
            const observer = new MutationObserver(() => {
                classifyCollapseIcons();
            });
            observer.observe(deckList, {
                childList: true,
                subtree: true
            });
        }
    });
})();
