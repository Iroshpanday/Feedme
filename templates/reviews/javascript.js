// Enhanced Search Autocomplete - Add this to your products page template

class ProductSearchAutocomplete {
    constructor() {
        this.searchInput = document.getElementById('searchInput');
        this.suggestionsContainer = null;
        this.currentFocus = -1;
        this.searchTimeout = null;
        
        this.init();
    }
    
    init() {
        this.createSuggestionsContainer();
        this.bindEvents();
    }
    
    createSuggestionsContainer() {
        this.suggestionsContainer = document.createElement('div');
        this.suggestionsContainer.className = 'search-suggestions';
        this.suggestionsContainer.style.cssText = `
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: white;
            border: 1px solid #e9ecef;
            border-top: none;
            border-radius: 0 0 10px 10px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            max-height: 400px;
            overflow-y: auto;
            z-index: 1000;
            display: none;
        `;
        
        this.searchInput.parentNode.style.position = 'relative';
        this.searchInput.parentNode.appendChild(this.suggestionsContainer);
    }
    
    bindEvents() {
        // Input event for search
        this.searchInput.addEventListener('input', (e) => {
            clearTimeout(this.searchTimeout);
            const query = e.target.value.trim();
            
            if (query.length >= 2) {
                this.searchTimeout = setTimeout(() => {
                    this.performSearch(query);
                }, 300);
            } else {
                this.hideSuggestions();
            }
        });
        
        // Keyboard navigation
        this.searchInput.addEventListener('keydown', (e) => {
            const suggestions = this.suggestionsContainer.querySelectorAll('.suggestion-item');
            
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                this.currentFocus++;
                this.addActive(suggestions);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                this.currentFocus--;
                this.addActive(suggestions);
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (this.currentFocus > -1 && suggestions[this.currentFocus]) {
                    suggestions[this.currentFocus].click();
                } else {
                    // Submit form if no suggestion selected
                    this.searchInput.closest('form').submit();
                }
            } else if (e.key === 'Escape') {
                this.hideSuggestions();
                this.searchInput.blur();
            }
        });
        
        // Hide suggestions when clicking outside
        document.addEventListener('click', (e) => {
            if (!this.searchInput.contains(e.target) && !this.suggestionsContainer.contains(e.target)) {
                this.hideSuggestions();
            }
        });
        
        // Show suggestions when focusing on input with existing value
        this.searchInput.addEventListener('focus', (e) => {
            if (e.target.value.trim().length >= 2) {
                this.performSearch(e.target.value.trim());
            }
        });
    }
    
    async performSearch(query) {
        try {
            const response = await fetch(`/api/product-autocomplete/?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            
            if (data.suggestions && data.suggestions.length > 0) {
                this.displaySuggestions(data.suggestions, query);
            } else {
                this.displayNoResults(query);
            }
        } catch (error) {
            console.error('Search error:', error);
            this.hideSuggestions();
        }
    }
    
    displaySuggestions(suggestions, query) {
        this.currentFocus = -1;
        let html = '<div class="suggestions-header">Search Results</div>';
        
        suggestions.forEach((suggestion, index) => {
            const highlightedName = this.highlightMatch(suggestion.name, query);
            
            if (suggestion.type === 'product') {
                html += `
                    <div class="suggestion-item product-suggestion" data-url="${suggestion.url}">
                        <div class="suggestion-image">
                            ${suggestion.image ? 
                                `<img src="${suggestion.image}" alt="${suggestion.name}" />` : 
                                '<i class="fas fa-mobile-alt"></i>'
                            }
                        </div>
                        <div class="suggestion-content">
                            <div class="suggestion-name">${highlightedName}</div>
                            <div class="suggestion-meta">
                                <span class="brand-name">${suggestion.brand}</span>
                                ${suggestion.rating > 0 ? 
                                    `<span class="rating">
                                        <i class="fas fa-star"></i> ${suggestion.rating.toFixed(1)}
                                    </span>` : ''
                                }
                                <span class="review-count">${suggestion.reviews} reviews</span>
                            </div>
                        </div>
                        <div class="suggestion-arrow">
                            <i class="fas fa-arrow-right"></i>
                        </div>
                    </div>
                `;
            } else if (suggestion.type === 'brand') {
                html += `
                    <div class="suggestion-item brand-suggestion" data-url="${suggestion.url}">
                        <div class="suggestion-image">
                            ${suggestion.image ? 
                                `<img src="${suggestion.image}" alt="${suggestion.name}" />` : 
                                '<i class="fas fa-tag"></i>'
                            }
                        </div>
                        <div class="suggestion-content">
                            <div class="suggestion-name">${highlightedName}</div>
                            <div class="suggestion-meta">Brand</div>
                        </div>
                        <div class="suggestion-arrow">
                            <i class="fas fa-arrow-right"></i>
                        </div>
                    </div>
                `;
            }
        });
        
        // Add "View all results" option
        html += `
            <div class="suggestion-item view-all" data-search="${query}">
                <div class="suggestion-content">
                    <div class="suggestion-name">
                        <i class="fas fa-search"></i>
                        View all results for "${query}"
                    </div>
                </div>
                <div class="suggestion-arrow">
                    <i class="fas fa-arrow-right"></i>
                </div>
            </div>
        `;
        
        this.suggestionsContainer.innerHTML = html;
        this.showSuggestions();
        this.bindSuggestionEvents();
    }
    
    displayNoResults(query) {
        const html = `
            <div class="suggestions-header">No Results Found</div>
            <div class="no-results-suggestion">
                <i class="fas fa-search"></i>
                <div>No products found for "${query}"</div>
                <small>Try different keywords or browse categories</small>
            </div>
        `;
        
        this.suggestionsContainer.innerHTML = html;
        this.showSuggestions();
    }
    
    bindSuggestionEvents() {
        const suggestionItems = this.suggestionsContainer.querySelectorAll('.suggestion-item');
        
        suggestionItems.forEach((item, index) => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                
                if (item.classList.contains('view-all')) {
                    // Search for all results
                    const searchQuery = item.dataset.search;
                    this.searchInput.value = searchQuery;
                    this.searchInput.closest('form').submit();
                } else {
                    // Navigate to specific product/brand
                    const url = item.dataset.url;
                    if (url) {
                        window.location.href = url;
                    }
                }
            });
            
            item.addEventListener('mouseenter', () => {
                this.removeActive();
                this.currentFocus = index;
                this.addActive(suggestionItems);
            });
        });
    }
    
    highlightMatch(text, query) {
        const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\            max-height: 400px;
            ')})`, 'gi');
        return text.replace(regex, '<mark>$1</mark>');
    }
    
    addActive(suggestions) {
        this.removeActive();
        if (this.currentFocus >= suggestions.length) this.currentFocus = 0;
        if (this.currentFocus < 0) this.currentFocus = suggestions.length - 1;
        
        if (suggestions[this.currentFocus]) {
            suggestions[this.currentFocus].classList.add('active');
        }
    }
    
    removeActive() {
        const suggestions = this.suggestionsContainer.querySelectorAll('.suggestion-item');
        suggestions.forEach(item => item.classList.remove('active'));
    }
    
    showSuggestions() {
        this.suggestionsContainer.style.display = 'block';
    }
    
    hideSuggestions() {
        this.suggestionsContainer.style.display = 'none';
        this.currentFocus = -1;
    }
}

// CSS Styles for autocomplete (add to your stylesheet)
const autocompleteStyles = `
    .search-suggestions {
        font-family: inherit;
    }
    
    .suggestions-header {
        padding: 0.75rem 1rem;
        background: #f8f9fa;
        font-weight: 600;
        font-size: 0.9rem;
        color: #666;
        border-bottom: 1px solid #e9ecef;
    }
    
    .suggestion-item {
        display: flex;
        align-items: center;
        padding: 0.75rem 1rem;
        cursor: pointer;
        border-bottom: 1px solid #f1f3f4;
        transition: background-color 0.2s;
    }
    
    .suggestion-item:hover,
    .suggestion-item.active {
        background-color: #f8f9fa;
    }
    
    .suggestion-item:last-child {
        border-bottom: none;
    }
    
    .suggestion-image {
        width: 40px;
        height: 40px;
        margin-right: 0.75rem;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #f8f9fa;
        border-radius: 6px;
        overflow: hidden;
    }
    
    .suggestion-image img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    
    .suggestion-image i {
        color: #666;
        font-size: 1.2rem;
    }
    
    .suggestion-content {
        flex: 1;
    }
    
    .suggestion-name {
        font-weight: 600;
        margin-bottom: 0.25rem;
        color: #333;
    }
    
    .suggestion-name mark {
        background: #fff3cd;
        color: #856404;
        padding: 0.1rem 0.2rem;
        border-radius: 3px;
    }
    
    .suggestion-meta {
        font-size: 0.85rem;
        color: #666;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .brand-name {
        color: #ff6b35;
        font-weight: 500;
    }
    
    .rating {
        display: flex;
        align-items: center;
        gap: 0.25rem;
        color: #ffc107;
    }
    
    .rating i {
        font-size: 0.8rem;
    }
    
    .suggestion-arrow {
        color: #ccc;
        margin-left: 0.5rem;
    }
    
    .view-all {
        background: #f8f9fa;
        font-weight: 500;
        color: #ff6b35;
    }
    
    .view-all:hover {
        background: #e9ecef;
    }
    
    .no-results-suggestion {
        text-align: center;
        padding: 2rem 1rem;
        color: #666;
    }
    
    .no-results-suggestion i {
        font-size: 2rem;
        margin-bottom: 0.5rem;
        color: #dee2e6;
    }
    
    .no-results-suggestion small {
        display: block;
        margin-top: 0.5rem;
        color: #999;
    }
`;

// Initialize autocomplete when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Add styles to head
    const styleElement = document.createElement('style');
    styleElement.textContent = autocompleteStyles;
    document.head.appendChild(styleElement);
    
    // Initialize autocomplete
    if (document.getElementById('searchInput')) {
        new ProductSearchAutocomplete();
    }
});

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ProductSearchAutocomplete;
}