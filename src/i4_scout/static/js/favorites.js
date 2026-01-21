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
            const listingId = parseInt(row.dataset.href.split('/').pop(), 10);
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
    };

    // Initialize on page load
    function init() {
        updateFavoriteButtons();
        updateFavoritesFilter();
    }

    // Run init on DOMContentLoaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Re-init after HTMX swaps (for pagination)
    document.body.addEventListener('htmx:afterSwap', function(evt) {
        if (evt.target.id === 'listings-table' || evt.target.closest('#listings-table')) {
            updateFavoriteButtons();

            // Re-apply favorites filter if checked
            const favoritesCheckbox = document.getElementById('favorites-only');
            if (favoritesCheckbox && favoritesCheckbox.checked) {
                filterFavoritesOnly(favoritesCheckbox);
            }
        }
    });
})();
