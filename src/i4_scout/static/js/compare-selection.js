/**
 * Compare selection state management for i4-scout
 * Uses localStorage to persist selections across browser sessions
 */
(function() {
    'use strict';

    const STORAGE_KEY = 'i4scout_compare_selections';
    const MAX_SELECTIONS = 4;

    // Get selections from localStorage
    function getSelections() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            return stored ? JSON.parse(stored) : [];
        } catch (e) {
            return [];
        }
    }

    // Save selections to localStorage
    function saveSelections(selections) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(selections));
    }

    // Toggle selection for a listing
    window.toggleSelection = function(checkbox) {
        const listingId = parseInt(checkbox.dataset.listingId, 10);
        const title = checkbox.dataset.listingTitle;
        const price = checkbox.dataset.listingPrice;

        let selections = getSelections();

        if (checkbox.checked) {
            // Check max limit
            if (selections.length >= MAX_SELECTIONS) {
                checkbox.checked = false;
                alert('Maximum ' + MAX_SELECTIONS + ' listings can be compared at once.');
                return;
            }
            // Add if not already in list
            if (!selections.find(s => s.id === listingId)) {
                selections.push({ id: listingId, title: title, price: price });
            }
        } else {
            // Remove from list
            selections = selections.filter(s => s.id !== listingId);
        }

        saveSelections(selections);
        updateUI();
    };

    // Select/deselect all visible checkboxes
    window.toggleSelectAll = function(checkbox) {
        const checkboxes = document.querySelectorAll('.listing-checkbox');
        let selections = getSelections();

        if (checkbox.checked) {
            // Add visible listings up to max
            checkboxes.forEach(cb => {
                if (selections.length >= MAX_SELECTIONS) {
                    cb.checked = false;
                    return;
                }
                const listingId = parseInt(cb.dataset.listingId, 10);
                if (!selections.find(s => s.id === listingId)) {
                    selections.push({
                        id: listingId,
                        title: cb.dataset.listingTitle,
                        price: cb.dataset.listingPrice
                    });
                    cb.checked = true;
                }
            });
        } else {
            // Remove all visible listings from selections
            const visibleIds = Array.from(checkboxes).map(cb => parseInt(cb.dataset.listingId, 10));
            selections = selections.filter(s => !visibleIds.includes(s.id));
            checkboxes.forEach(cb => cb.checked = false);
        }

        saveSelections(selections);
        updateUI();
    };

    // Clear all selections
    window.clearSelections = function() {
        localStorage.removeItem(STORAGE_KEY);
        document.querySelectorAll('.listing-checkbox').forEach(cb => cb.checked = false);
        const selectAll = document.getElementById('select-all');
        if (selectAll) selectAll.checked = false;
        updateUI();
    };

    // Navigate to comparison page
    window.goToCompare = function() {
        const selections = getSelections();
        if (selections.length < 2) {
            alert('Please select at least 2 listings to compare.');
            return;
        }
        const ids = selections.map(s => s.id).join(',');
        window.location.href = '/compare?ids=' + ids;
    };

    // Update UI to reflect current selection state
    function updateUI() {
        const selections = getSelections();
        const count = selections.length;
        const selectedIds = selections.map(s => s.id);

        // Update compare bar visibility and content
        const bar = document.getElementById('compare-bar');
        const countEl = document.getElementById('compare-count');
        const compareBtn = document.getElementById('compare-btn');
        const maxHint = document.getElementById('compare-max-hint');

        if (bar) {
            if (count > 0) {
                bar.hidden = false;
                countEl.textContent = count;
                compareBtn.disabled = count < 2;
                if (maxHint) maxHint.hidden = count < MAX_SELECTIONS;
            } else {
                bar.hidden = true;
            }
        }

        // Sync checkbox states with stored selections
        document.querySelectorAll('.listing-checkbox').forEach(cb => {
            const listingId = parseInt(cb.dataset.listingId, 10);
            cb.checked = selectedIds.includes(listingId);
        });

        // Update select-all checkbox state
        const selectAll = document.getElementById('select-all');
        if (selectAll) {
            const checkboxes = document.querySelectorAll('.listing-checkbox');
            const checkedCount = Array.from(checkboxes).filter(cb => cb.checked).length;
            selectAll.checked = checkboxes.length > 0 && checkedCount === checkboxes.length;
            selectAll.indeterminate = checkedCount > 0 && checkedCount < checkboxes.length;
        }
    }

    // Initialize on page load
    function init() {
        // Attach select-all handler
        const selectAll = document.getElementById('select-all');
        if (selectAll) {
            selectAll.addEventListener('change', function() {
                toggleSelectAll(this);
            });
        }

        // Restore checkbox states from storage
        updateUI();
    }

    // Run init on DOMContentLoaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Re-init after HTMX swaps (for pagination)
    document.body.addEventListener('htmx:afterSwap', function(evt) {
        // Only re-init if the listings table was updated
        if (evt.target.id === 'listings-table' || evt.target.closest('#listings-table')) {
            updateUI();
            // Re-attach select-all handler if it was replaced
            const selectAll = document.getElementById('select-all');
            if (selectAll && !selectAll._hasHandler) {
                selectAll.addEventListener('change', function() {
                    toggleSelectAll(this);
                });
                selectAll._hasHandler = true;
            }
        }
    });
})();
