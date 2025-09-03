// Onigiri Add-on: injector.js

// This script is injected into the Deck Browser to handle interactions
// with the custom sidebar.

(function() {
    // --- Sidebar Resize Logic ---
    document.addEventListener('DOMContentLoaded', (event) => {
        const handle = document.querySelector('.resize-handle');
        const sidebar = document.querySelector('.sidebar-left');
        
        if (!handle || !sidebar) return;

        let isResizing = false;

        handle.addEventListener('mousedown', function(e) {
            isResizing = true;
            document.body.style.userSelect = 'none';
            document.body.style.cursor = 'col-resize';
        });

        document.addEventListener('mousemove', function(e) {
            if (!isResizing) return;
            // The sidebar width is the mouse's X position relative to the start of the window.
            let newWidth = e.clientX;
            // Clamp the width between reasonable min/max values.
            if (newWidth < 200) newWidth = 200;
            if (newWidth > 500) newWidth = 500;
            sidebar.style.width = newWidth + 'px';
        });

        document.addEventListener('mouseup', function(e) {
            if (isResizing) {
                isResizing = false;
                document.body.style.removeProperty('user-select');
                document.body.style.removeProperty('cursor');
                // Save the new width to Anki's config using the standard pycmd function
                const finalWidth = parseInt(sidebar.style.width);
                if (typeof pycmd === 'function') {
                    pycmd(`saveSidebarWidth:${finalWidth}`);
                }
            }
        });
    });
})();