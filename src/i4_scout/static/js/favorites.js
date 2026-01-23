/**
 * Favorites management for i4-scout
 * Uses localStorage to persist favorites across browser sessions
 */
(function() {
    'use strict';

    const STORAGE_KEY = 'i4scout_favorites';

    // Get favorites from localStorage
    function getFavorites() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            return stored ? JSON.parse(stored) : [];
        } catch (e) {
            return [];
        }
    }

    // Save favorites to localStorage
    function saveFavorites(favorites) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites));
    }

    // Check if a listing is favorited
    window.isFavorite = function(listingId) {
        const favorites = getFavorites();
        return favorites.includes(listingId);
    };

    // Toggle favorite status for a listing
    window.toggleFavorite = function(listingId, event) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }

        listingId = parseInt(listingId, 10);
        let favorites = getFavorites();

        if (favorites.includes(listingId)) {
            favorites = favorites.filter(id => id !== listingId);
        } else {
            favorites.push(listingId);
        }

        saveFavorites(favorites);
        updateFavoriteButtons();
        updateFavoritesFilter();

        return false;
    };

    // Update all favorite buttons to reflect current state
    function updateFavoriteButtons() {
        const favorites = getFavorites();

        document.querySelectorAll('.favorite-btn').forEach(btn => {
            const listingId = parseInt(btn.dataset.listingId, 10);
            const isFav = favorites.includes(listingId);

            btn.classList.toggle('is-favorite', isFav);
            btn.setAttribute('aria-pressed', isFav.toString());
            btn.title = isFav ? 'Remove from favorites' : 'Add to favorites';

            // Handle both small (icon only) and large (icon + text) variants
            if (btn.classList.contains('favorite-btn-large')) {
                btn.innerHTML = isFav ? '&#x2605; Favorited' : '&#x2606; Favorite';
            } else {
                btn.innerHTML = isFav ? '&#x2605;' : '&#x2606;';
            }
        });
    }

    // Update favorites filter display (count badge)
    function updateFavoritesFilter() {
        const favorites = getFavorites();
        const countEl = document.getElementById('favorites-count');
        if (countEl) {
            countEl.textContent = favorites.length > 0 ? ` (${favorites.length})` : '';
        }
    }

    // Filter listings to show only favorites (client-side)
    window.filterFavoritesOnly = function(checkbox) {
        const showFavoritesOnly = checkbox.checked;
        const favorites = getFavorites();

        document.querySelectorAll('.listing-row').forEach(row => {
            // Use data-listing-id directly (more reliable than parsing data-href)
            const listingId = parseInt(row.dataset.listingId, 10);
            if (showFavoritesOnly && !favorites.includes(listingId)) {
                row.style.display = 'none';
            } else {
                row.style.display = '';
            }
        });

        // Update pagination info
        if (showFavoritesOnly) {
            const visibleRows = document.querySelectorAll('.listing-row:not([style*="display: none"])').length;
            const paginationInfo = document.querySelector('.pagination-info');
            if (paginationInfo) {
                paginationInfo.dataset.originalText = paginationInfo.textContent;
                paginationInfo.textContent = `Showing ${visibleRows} favorite(s)`;
            }
        } else {
            const paginationInfo = document.querySelector('.pagination-info');
            if (paginationInfo && paginationInfo.dataset.originalText) {
                paginationInfo.textContent = paginationInfo.dataset.originalText;
            }
        }

        // Update URL with favorites_only param
        const url = new URL(window.location.href);
        if (showFavoritesOnly) {
            url.searchParams.set('favorites_only', 'true');
        } else {
            url.searchParams.delete('favorites_only');
        }
        window.history.replaceState({}, '', url.toString());
    };

    // Check URL for favorites_only param on init and restore state
    function restoreFavoritesFilterFromUrl() {
        const url = new URL(window.location.href);
        const favoritesOnly = url.searchParams.get('favorites_only') === 'true';
        const checkbox = document.getElementById('favorites-only');
        if (checkbox && favoritesOnly) {
            checkbox.checked = true;
            filterFavoritesOnly(checkbox);
        }
    }

    // Initialize on page load
    function init() {
        updateFavoriteButtons();
        updateFavoritesFilter();
        restoreFavoritesFilterFromUrl();
    }

    // Run init on DOMContentLoaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Re-init after HTMX swaps (for pagination)
    document.body.addEventListener('htmx:afterSwap', function(evt) {
        // HTMX uses evt.detail.target for the swap target, evt.target is the element that triggered the event
        const swapTarget = evt.detail && evt.detail.target ? evt.detail.target : evt.target;
        if (swapTarget.id === 'listings-table' || swapTarget.closest('#listings-table')) {
            updateFavoriteButtons();

            // Re-apply favorites filter if checked
            const favoritesCheckbox = document.getElementById('favorites-only');
            if (favoritesCheckbox && favoritesCheckbox.checked) {
                filterFavoritesOnly(favoritesCheckbox);
            }
        }
    });
})();
