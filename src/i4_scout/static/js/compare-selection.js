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

    // Copy selected listings to clipboard in LLM-friendly format
    window.copyToClipboard = async function() {
        const selections = getSelections();
        if (selections.length === 0) {
            return;
        }

        const copyBtn = document.getElementById('copy-btn');
        const originalText = copyBtn.textContent;

        try {
            // Show loading state
            copyBtn.textContent = 'Copying...';
            copyBtn.disabled = true;

            // Fetch full details for each listing, their notes, and options config in parallel
            const [listings, notesArrays, configRes] = await Promise.all([
                Promise.all(selections.map(s =>
                    fetch('/api/listings/' + s.id).then(r => r.json())
                )),
                Promise.all(selections.map(s =>
                    fetch('/api/listings/' + s.id + '/notes').then(r => r.json())
                )),
                fetch('/api/config/options').then(r => r.json())
            ]);

            // Attach notes to each listing
            listings.forEach((listing, i) => {
                listing.notes = notesArrays[i] || [];
            });

            // Format as LLM-friendly markdown
            const text = formatListingsForLLM(listings, configRes);

            // Copy to clipboard
            await navigator.clipboard.writeText(text);

            // Show success feedback
            copyBtn.textContent = 'Copied!';
            copyBtn.classList.add('copy-success');
            setTimeout(() => {
                copyBtn.textContent = originalText;
                copyBtn.disabled = false;
                copyBtn.classList.remove('copy-success');
            }, 2000);
        } catch (err) {
            console.error('Failed to copy:', err);
            copyBtn.textContent = 'Failed';
            copyBtn.classList.add('copy-error');
            setTimeout(() => {
                copyBtn.textContent = originalText;
                copyBtn.disabled = false;
                copyBtn.classList.remove('copy-error');
            }, 2000);
        }
    };

    // Format listings as LLM-friendly markdown
    function formatListingsForLLM(listings, config) {
        const lines = ['# Car Listings Comparison', ''];

        listings.forEach((listing, index) => {
            // Header
            lines.push('## Listing ' + (index + 1) + ': ' + (listing.title || 'Untitled'));

            // Basic info
            if (listing.price !== null && listing.price !== undefined) {
                lines.push('- **Price:** €' + listing.price.toLocaleString('de-DE'));
            }
            if (listing.mileage_km !== null && listing.mileage_km !== undefined) {
                lines.push('- **Mileage:** ' + listing.mileage_km.toLocaleString('de-DE') + ' km');
            }
            if (listing.first_registration_year) {
                lines.push('- **Year:** ' + listing.first_registration_year);
            }

            // Location
            const locationParts = [];
            if (listing.location_city) locationParts.push(listing.location_city);
            if (listing.location_country) locationParts.push(listing.location_country);
            if (locationParts.length > 0) {
                lines.push('- **Location:** ' + locationParts.join(', '));
            }

            // Dealer
            if (listing.dealer_name) {
                const dealerType = listing.dealer_type ? ' (' + listing.dealer_type + ')' : '';
                lines.push('- **Dealer:** ' + listing.dealer_name + dealerType);
            }

            // Match score
            if (listing.match_score !== null && listing.match_score !== undefined) {
                const qualified = listing.is_qualified ? 'Yes' : 'No';
                lines.push('- **Match Score:** ' + listing.match_score.toFixed(0) + '% (Qualified: ' + qualified + ')');
            }

            // Issue status
            if (listing.has_issue) {
                lines.push('- **Issue:** Yes (flagged)');
            }

            // URL
            if (listing.url) {
                lines.push('- **URL:** ' + listing.url);
            }

            lines.push('');

            // Matched options
            const matchedOptions = listing.matched_options || [];
            if (matchedOptions.length > 0) {
                lines.push('### Matched Options');
                matchedOptions.forEach(opt => {
                    lines.push('- ' + opt);
                });
                lines.push('');
            }

            // Missing required options (from config)
            if (config && config.required) {
                const requiredNames = config.required.map(opt => opt.name);
                const missingRequired = requiredNames.filter(name => !matchedOptions.includes(name));
                if (missingRequired.length > 0) {
                    lines.push('### Missing Required Options');
                    missingRequired.forEach(opt => {
                        lines.push('- ' + opt);
                    });
                    lines.push('');
                }
            }

            // Notes (if any)
            const notes = listing.notes || [];
            if (notes.length > 0) {
                lines.push('### Notes');
                notes.forEach(note => {
                    const timestamp = note.created_at ? new Date(note.created_at).toLocaleString() : '';
                    lines.push('- [' + timestamp + '] ' + note.content);
                });
                lines.push('');
            }

            // Separator between listings (except last)
            if (index < listings.length - 1) {
                lines.push('---');
                lines.push('');
            }
        });

        return lines.join('\n');
    }

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
