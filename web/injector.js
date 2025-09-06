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
    let startX;
    let startWidth;
    let animationFrameId = null; // To hold the requestAnimationFrame ID
    let lastClientX = 0; // To store the latest mouse position

    // The update function to be called by the browser before the next repaint
    const updateSidebarWidth = () => {
        const deltaX = lastClientX - startX;
        let newWidth = startWidth + deltaX;

        // Enforce min and max widths
        if (newWidth < 100) newWidth = 100;
        if (newWidth > 800) newWidth = 800;

        sidebarEl.style.width = `${newWidth}px`;

        // Allow the next animation frame to be scheduled
        animationFrameId = null;
    };

    // Make the indicator follow the cursor precisely within the handle area
    handle.addEventListener('mousemove', (e) => {
        if (isResizing) return;
        const rect = handle.getBoundingClientRect();
        const y = Math.max(0, Math.min(rect.height, e.clientY - rect.top));
        const yPercentage = (y / rect.height) * 100;
        handle.style.setProperty('--handle-top', `${yPercentage}%`);
    });

    handle.addEventListener('mouseleave', () => {
        if (!isResizing) {
            handle.style.setProperty('--handle-top', '50%');
        }
    });

    // Start the resizing process
    handle.addEventListener('mousedown', (e) => {
        isResizing = true;
        startX = e.clientX;
        lastClientX = e.clientX;
        startWidth = sidebarEl.offsetWidth;

        sidebarEl.classList.add('is-resizing');
        handle.classList.add('is-resizing');
        // Give the browser a performance hint
        sidebarEl.style.willChange = 'width'; 
        document.body.style.userSelect = 'none';
        document.body.style.cursor = 'col-resize';
    });

    // Handle the actual sidebar resizing
    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;
        lastClientX = e.clientX; // Update the last known mouse position

        // If an update isn't already scheduled, schedule one
        if (!animationFrameId) {
            animationFrameId = requestAnimationFrame(updateSidebarWidth);
        }
    });

    // Stop resizing and reset everything
    document.addEventListener('mouseup', () => {
        if (isResizing) {
            // Cancel any pending frame if the mouse is released
            if (animationFrameId) {
                cancelAnimationFrame(animationFrameId);
                animationFrameId = null;
            }

            isResizing = false;
            sidebarEl.classList.remove('is-resizing');
            handle.classList.remove('is-resizing');
            // Remove the performance hint
            sidebarEl.style.willChange = 'auto'; 
            document.body.style.removeProperty('user-select');
            document.body.style.removeProperty('cursor');

            handle.style.setProperty('--handle-top', '50%');

            // Save the final width to config
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
