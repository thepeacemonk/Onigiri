// Onigiri Performance Engine

window.OnigiriEngine = {
    currentHoveredRow: null,

    init: function() {
        this.deckListContainer = document.getElementById('deck-list-container');
        if (!this.deckListContainer) {
            return;
        }

        this.bindEvents();
        this.observeMutations();

        // Initial processing of already loaded nodes
        this.processNewNodes(document.querySelectorAll('tr.deck, a.collapse'));
        this.restoreScrollPosition();
    },

    /**
     * Replaces the deck tree's HTML content without a full page reload,
     * preserving scroll position.
     * @param {string} newHtml The new HTML for the deck tree's <tbody>.
     */
    updateDeckTree: function(newHtml) {
        if (!this.deckListContainer) return;
        
        const tableBody = this.deckListContainer.querySelector('table.deck-table tbody');
        if (!tableBody) return;

        this.deckListContainer.classList.add('scroll-restoring');
        tableBody.innerHTML = newHtml;
        this.restoreScrollPosition();
        this.processNewNodes(tableBody.children);
        
        if (typeof window.updateDeckLayouts === 'function') {
            window.updateDeckLayouts();
        }

        setTimeout(() => {
            this.deckListContainer.classList.remove('scroll-restoring');
        }, 50);
    },

    /** Saves the current scroll position to session storage. */
    saveScrollPosition: function() {
        if (this.deckListContainer) {
            sessionStorage.setItem('deckListScrollTop', this.deckListContainer.scrollTop);
        }
    },

    /** Restores the scroll position from session storage. */
    restoreScrollPosition: function() {
        const savedScroll = sessionStorage.getItem('deckListScrollTop');
        if (savedScroll !== null && this.deckListContainer) {
            this.deckListContainer.scrollTop = parseInt(savedScroll, 10);
        }
    },

    /** Binds event listeners to handle interactions. */
    bindEvents: function() {
        if (this.deckListContainer.dataset.engineBound) return;
        this.deckListContainer.dataset.engineBound = 'true';

        // --- Listener: Keep row hovered while mouse is over it ---
        this.deckListContainer.addEventListener('mouseenter', (event) => {
            const deckRow = event.target.closest('tr.deck');
            if (deckRow) {
                this.currentHoveredRow = deckRow;
                deckRow.classList.add('is-hovered');
            }
        }, true);

        this.deckListContainer.addEventListener('mouseleave', (event) => {
            const deckRow = event.target.closest('tr.deck');
            if (deckRow && deckRow === this.currentHoveredRow) {
                deckRow.classList.remove('is-hovered');
                this.currentHoveredRow = null;
            }
        }, true);

        // --- Listener: Restrict drag-and-drop to Editing Mode ---
        this.deckListContainer.addEventListener('dragstart', (event) => {
            const isEditingMode = this.deckListContainer.classList.contains('editing-mode') ||
                                  document.body.classList.contains('editing-mode');
            if (!isEditingMode) {
                event.preventDefault();
                event.stopPropagation();
                return false;
            }

            // Set custom drag image for better cursor alignment (adjust offsets as needed)
            const dragElement = event.target.closest('tr.deck'); // Use the dragged deck row or customize
            if (dragElement && event.dataTransfer) {
                const dragImage = dragElement.cloneNode(true); // Clone for preview
                dragImage.style.opacity = '0.8'; // Optional: Make preview semi-transparent
                dragImage.style.transform = 'scale(0.9)'; // Optional: Slightly shrink for better UX
                event.dataTransfer.setDragImage(dragImage, -10, -10); // Offset to align closer to cursor (x, y in pixels)
            }
        });

        // --- Listener: Handle Collapse ---
        this.deckListContainer.addEventListener('click', (event) => {
            const collapseLink = event.target.closest('a.collapse');
            if (collapseLink) {
                this.saveScrollPosition();
                return;
            }
        });

        // --- Listener: Handle Double-click ---
        let clickTimer = null;
        this.deckListContainer.addEventListener('click', (event) => {
            if (event.target.closest('.opts')) return;
            if (event.target.closest('a.collapse')) return;

            const deckRow = event.target.closest('tr.deck');
            if (deckRow) {
                if (!deckRow.dataset.clickCount) deckRow.dataset.clickCount = 0;
                deckRow.dataset.clickCount++;

                if (parseInt(deckRow.dataset.clickCount, 10) === 1) {
                    clickTimer = setTimeout(() => { deckRow.dataset.clickCount = 0; }, 300);
                } else if (parseInt(deckRow.dataset.clickCount, 10) === 2) {
                    clearTimeout(clickTimer);
                    deckRow.dataset.clickCount = 0;
                    const mainLink = deckRow.querySelector('a.deck');
                    if (mainLink) mainLink.click();
                }
            }
        });
    },

    /** Watches for changes in the deck list and processes ONLY new elements. */
    observeMutations: function() {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach(mutation => {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    this.processNewNodes(mutation.addedNodes);
                }
            });
            if (typeof window.updateDeckLayouts === 'function') {
                window.updateDeckLayouts();
            }
        });

        observer.observe(this.deckListContainer, {
            childList: true,
            subtree: true,
        });
    },

    /** Processes a list of new nodes, classifying icons and adding styles. */
    processNewNodes: function(nodes) {
        nodes.forEach(node => {
            if (node.nodeType !== Node.ELEMENT_NODE) return;

            const elementsToProcess = [];
            if (node.matches('a.collapse, tr.deck')) {
                elementsToProcess.push(node);
            }
            elementsToProcess.push(...node.querySelectorAll('a.collapse, tr.deck'));

            elementsToProcess.forEach(el => {
                if (el.matches('a.collapse')) {
                    this.classifyCollapseIcon(el);
                } else if (el.matches('tr.deck')) {
                    const clickableCell = el.querySelector('td.decktd');
                    if (clickableCell) clickableCell.style.cursor = 'pointer';
                }
            });
        });
    },

    /** Applies open/closed state classes to a collapse icon. */
    classifyCollapseIcon: function(el) {
        if (el.dataset.onigiriClassified) return;
        el.dataset.onigiriClassified = 'true';
        el.classList.remove('state-open', 'state-closed');
        
        if (el.textContent.trim() === '-') {
            el.classList.add('state-open');
        } else {
            el.classList.add('state-closed');
        }
        el.textContent = '';
    },
};

// Initialize the engine once the DOM is ready.
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => OnigiriEngine.init());
} else {
    OnigiriEngine.init();
}