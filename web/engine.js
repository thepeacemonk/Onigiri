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

        // --- START: New flicker-fix logic ---
        if (typeof OnigiriEditor !== 'undefined' && OnigiriEditor.EDIT_MODE) {
            // 1. Create a temporary container
            const tempContainer = document.createElement('tbody');
            tempContainer.innerHTML = newHtml;
            
            // 2. Add checkboxes to the nodes in the temporary container
            tempContainer.querySelectorAll('tr.deck').forEach(row => {
                const did = row.dataset.did; // Relies on data-did from patcher.py
                if (!did) return;

                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.className = 'deck-checkbox';
                checkbox.dataset.did = did;
                
                // Restore the 'checked' state from the editor's memory
                checkbox.checked = OnigiriEditor.SELECTED_DECKS.has(did);

                checkbox.onclick = (e) => {
                    e.stopPropagation();
                    if (e.target.checked) {
                        OnigiriEditor.SELECTED_DECKS.add(e.target.dataset.did);
                    } else {
                        OnigiriEditor.SELECTED_DECKS.delete(e.target.dataset.did);
                    }
                };

                const decktd = row.querySelector('td.decktd');
                if (decktd) {
                    decktd.prepend(checkbox);
                }
            });
            
            // 3. Replace the content with the *modified* nodes
            tableBody.innerHTML = ''; // Clear existing content
            tableBody.append(...tempContainer.childNodes); // Append new, modified nodes
            
        } else {
            // 4. If not in edit mode, use the fast original method
            tableBody.innerHTML = newHtml;
        }
        // --- END: New flicker-fix logic ---

        this.restoreScrollPosition();
        this.processNewNodes(tableBody.children); // Process new nodes (for collapse icons etc.)
        
        if (typeof window.updateDeckLayouts === 'function') {
            window.updateDeckLayouts();
        }

        // The logic below is no longer needed, as it's handled above
        // if (typeof OnigiriEditor !== 'undefined' && OnigiriEditor.EDIT_MODE) {
        //     OnigiriEditor.reapplyEditModeState();
        // }

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

        // --- Unified Click Handler for Deck List ---
        // This single listener handles both deck collapse and double-click-to-study.
        let clickTimer = null;
        this.deckListContainer.addEventListener('click', (event) => {
            const target = event.target;

            // Case 1: Click was on a collapse icon.
            // We save the scroll position and then simply let the event proceed.
            // The `onclick` attribute on the <a> tag will handle the pycmd call.
            // We must NOT call event.preventDefault() or return, as that would
            // block the pycmd from firing.
            const collapseLink = target.closest('a.collapse');
            if (collapseLink) {
                this.saveScrollPosition();
                // Allow the default action (onclick attribute) to happen.
                return; 
            }

            // Case 2: Click was on the options/gear icon. Ignore it.
            if (target.closest('.opts')) {
                return;
            }

            // Case 3: Click was on the favorite star. Ignore it.
            // This allows its own onclick attribute to fire without interference.
            if (target.closest('.favorite-star-icon')) {
                return;
            }

            // Case 3.5: Click was on the edit mode checkbox. Ignore it.
            if (target.closest('.deck-checkbox')) {
                return;
            }

            // Case 4: Click was on the deck row itself. Handle double-click to study.
            // This part of the listener will only be reached if the click was NOT on a collapse icon
            // AND not on the favorite star.
            const deckRow = target.closest('tr.deck');
            if (!deckRow) return;

            // Prevent the default link navigation, as we are managing it with a timer.
            event.preventDefault();

            if (!clickTimer) {
                // First click, start timer.
                clickTimer = setTimeout(() => { clickTimer = null; }, 300);
            } else {
                // Second click, fire study action and clear timer.
                clearTimeout(clickTimer);
                clickTimer = null;
                const mainLink = deckRow.querySelector('a.deck');
                if (mainLink) mainLink.click();
            }
        });

        // --- Listener: Restrict drag-and-drop to Editing Mode ---
        this.deckListContainer.addEventListener('dragstart', (event) => {
            const isEditingMode = document.body.classList.contains('deck-edit-mode');
            if (!isEditingMode) {
                event.preventDefault();
                event.stopPropagation();
                return false;
            }

            const dragElement = event.target.closest('tr.deck');
            if (dragElement && event.dataTransfer) {
                const dragImage = dragElement.cloneNode(true);
                dragImage.style.opacity = '0.8';
                dragImage.style.transform = 'scale(0.9)';
                event.dataTransfer.setDragImage(dragImage, -10, -10);
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