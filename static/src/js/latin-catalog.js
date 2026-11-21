/**
 * TINTORA — LATIN PRODUCTS catalog (Alpine.js component).
 *
 * The server renders every product card for the current page scope (all
 * products on /latin-products/, category subset on /latin-products/<cat>/).
 * This component powers dynamic search, category/brand filters, A–Z / Z–A
 * sorting and responsive pagination (12 / 16 / 24 per page) while keeping the
 * full filter state in the URL:
 *
 *   ?category=<slug>&search=<q>&brand=<name>&sort=catalog|az|za&page=<n>
 *
 * The embedded payload contains public dataset fields only — internal fields
 * (id, xref, sourcePage) never reach the browser.
 *
 * Motion always honours prefers-reduced-motion.
 */
(function () {
  'use strict';

  var LATIN_SORTS = ['catalog', 'az', 'za'];

  function latinNormalize(value) {
    return String(value || '')
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '');
  }

  function searchHaystack(product) {
    return latinNormalize(
      [product.name, product.nameEn, product.brand, product.category, product.subcategory, product.retailSize || product.packageSize].join(
        ' '
      )
    );
  }

  function compareNames(a, b) {
    return a.name.localeCompare(b.name, 'es', { sensitivity: 'base' });
  }

  function latinCatalog(initial) {
    initial = initial || {};
    var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // ------------------------------------------------------------------ //
    // Dataset (public fields only)                                       //
    // ------------------------------------------------------------------ //
    var payload = { products: [], categories: [] };
    var payloadEl = document.getElementById('latin-catalog-data');
    if (payloadEl) {
      try {
        payload = JSON.parse(payloadEl.textContent || '{}');
      } catch (error) {
        console.error('[latin-catalog] invalid dataset payload', error);
      }
    }

    var products = (payload.products || []).map(function (product) {
      return Object.assign({}, product, { _hay: searchHaystack(product) });
    });
    var categories = payload.categories || [];

    var mode = initial.mode === 'category' ? 'category' : 'index';

    var component = {
      // ----- state ----------------------------------------------------- //
      mode: mode,
      products: products,
      categories: categories,
      search: '',
      category: mode === 'category' ? initial.category || '' : '',
      brand: '',
      sort: 'catalog',
      page: 1,
      perPage: 24,

      // ----- lifecycle -------------------------------------------------- //
      init: function () {
        this.perPage = this._calcPerPage();
        this._readUrl();
        this.page = Math.min(Math.max(1, this.page), this.totalPages);

        var self = this;
        this._onResize = self._debounce(function () {
          var next = self._calcPerPage();
          if (next !== self.perPage) {
            self.perPage = next;
            if (self.page > self.totalPages) self.page = self.totalPages;
          }
        }, 150);
        this._onPopState = function () {
          self._readUrl();
          self.page = Math.min(Math.max(1, self.page), self.totalPages);
          self.syncUrl();
        };
        window.addEventListener('resize', this._onResize);
        window.addEventListener('popstate', this._onPopState);

        this.syncUrl();
      },

      destroy: function () {
        if (this._onResize) window.removeEventListener('resize', this._onResize);
        if (this._onPopState) window.removeEventListener('popstate', this._onPopState);
        if (this._searchTimer) window.clearTimeout(this._searchTimer);
      },

      // ----- derived data ------------------------------------------------ //
      get totalProducts() {
        return this.products.length;
      },

      get filtered() {
        var query = latinNormalize(this.search);
        var category = this.category;
        var brand = this.brand;
        var list = this.products.filter(function (product) {
          if (category && product.categorySlug !== category) return false;
          if (brand && product.brand !== brand) return false;
          if (query && product._hay.indexOf(query) === -1) return false;
          return true;
        });
        if (this.sort === 'az') list = list.slice().sort(compareNames);
        else if (this.sort === 'za') list = list.slice().sort(function (a, b) { return compareNames(b, a); });
        return list;
      },

      get totalPages() {
        return Math.max(1, Math.ceil(this.filtered.length / this.perPage));
      },

      get safePage() {
        return Math.min(this.page, this.totalPages);
      },

      get pageItems() {
        var start = (this.safePage - 1) * this.perPage;
        return this.filtered.slice(start, start + this.perPage);
      },

      get pageSlugs() {
        return this.pageItems.map(function (product) { return product.slug; });
      },

      get visiblePages() {
        var total = this.totalPages;
        var current = this.safePage;
        var pages = [];
        var push = function (n) {
          pages.push({ key: 'p' + n, n: n, current: n === current });
        };
        if (total <= 7) {
          for (var i = 1; i <= total; i++) push(i);
          return pages;
        }
        var wanted = [1, total, current - 1, current, current + 1].filter(function (n, i, all) {
          return n >= 1 && n <= total && all.indexOf(n) === i;
        });
        wanted.sort(function (a, b) { return a - b; });
        var previous = 0;
        for (var k = 0; k < wanted.length; k++) {
          var n = wanted[k];
          if (previous && n - previous > 1) pages.push({ key: 'gap-' + previous, n: null, current: false });
          push(n);
          previous = n;
        }
        return pages;
      },

      /** Per-category counts respecting current search + brand (not category). */
      get catCounts() {
        var query = latinNormalize(this.search);
        var brand = this.brand;
        var counts = {};
        for (var i = 0; i < this.products.length; i++) {
          var product = this.products[i];
          if (brand && product.brand !== brand) continue;
          if (query && product._hay.indexOf(query) === -1) continue;
          counts[product.categorySlug] = (counts[product.categorySlug] || 0) + 1;
        }
        return counts;
      },

      /** Per-brand counts respecting current search + category (not brand). */
      get brandCounts() {
        var query = latinNormalize(this.search);
        var category = this.category;
        var counts = {};
        for (var i = 0; i < this.products.length; i++) {
          var product = this.products[i];
          if (!product.brand) continue;
          if (category && product.categorySlug !== category) continue;
          if (query && product._hay.indexOf(query) === -1) continue;
          counts[product.brand] = (counts[product.brand] || 0) + 1;
        }
        return counts;
      },

      /** Distinct brands in the current payload, alphabetical. */
      get brandOptions() {
        var seen = {};
        for (var i = 0; i < this.products.length; i++) {
          var brand = this.products[i].brand;
          if (brand) seen[brand] = true;
        }
        return Object.keys(seen).sort(function (a, b) {
          return a.localeCompare(b, 'es', { sensitivity: 'base' });
        }).map(function (value) {
          return { value: value };
        });
      },

      // ----- card visibility (bound per server-rendered card) -------------- //
      isVisible: function (slug) {
        return this.pageSlugs.indexOf(slug) !== -1;
      },

      orderOf: function (slug) {
        var index = this.pageSlugs.indexOf(slug);
        return index === -1 ? 10000 : index;
      },

      // ----- actions ------------------------------------------------------- //
      onSearchInput: function (value) {
        var self = this;
        if (this._searchTimer) window.clearTimeout(this._searchTimer);
        this._searchTimer = window.setTimeout(function () {
          self.search = value;
          self.page = 1;
          self.syncUrl();
        }, 250);
      },

      onSortChange: function (value) {
        if (LATIN_SORTS.indexOf(value) === -1) return;
        this.sort = value;
        this.page = 1;
        this.syncUrl();
      },

      setCategory: function (slug) {
        if (this.mode !== 'index') return;
        this.category = this.category === slug ? '' : slug;
        this.page = 1;
        this.syncUrl();
      },

      setBrand: function (value) {
        this.brand = this.brand === value ? '' : value;
        this.page = 1;
        this.syncUrl();
      },

      clearFilters: function () {
        if (this._searchTimer) window.clearTimeout(this._searchTimer);
        this.search = '';
        this.brand = '';
        if (this.mode === 'index') this.category = '';
        this.page = 1;
        this.syncUrl();
      },

      goTo: function (target) {
        var page = Math.min(Math.max(1, target), this.totalPages);
        if (page === this.safePage) return;
        this.page = page;
        this.syncUrl();
        this.scrollToGrid();
      },

      chipClass: function (slug) {
        return this.mode === 'index' && this.category === slug ? 'latin-chip-active' : '';
      },

      scrollToGrid: function () {
        var grid = document.getElementById('latin-grid');
        if (!grid) return;
        var scrollTop = window.pageYOffset || document.documentElement.scrollTop || 0;
        var top = Math.max(grid.getBoundingClientRect().top + scrollTop - 150, 0);
        if (window.tintoraLenis && typeof window.tintoraLenis.scrollTo === 'function') {
          window.tintoraLenis.scrollTo(top, { immediate: reducedMotion, duration: 0.7 });
        } else {
          window.scrollTo({ top: top, behavior: reducedMotion ? 'auto' : 'smooth' });
        }
      },

      // ----- URL state ------------------------------------------------------ //
      syncUrl: function () {
        var params = new URLSearchParams();
        if (this.mode === 'index' && this.category) params.set('category', this.category);
        if (this.search.trim()) params.set('search', this.search.trim());
        if (this.brand) params.set('brand', this.brand);
        if (this.sort !== 'catalog') params.set('sort', this.sort);
        if (this.page > 1) params.set('page', String(this.page));
        var queryString = params.toString();
        var url = window.location.pathname + (queryString ? '?' + queryString : '');
        try {
          window.history.replaceState(null, '', url);
        } catch (error) {
          /* history API unavailable — filtering still works, state just is not shareable */
        }
      },

      _readUrl: function () {
        var params;
        try {
          params = new URLSearchParams(window.location.search);
        } catch (error) {
          return;
        }
        this.search = params.get('search') || '';
        this.brand = '';
        this.sort = 'catalog';
        if (this.mode === 'index') this.category = '';
        this.page = 1;

        var brand = params.get('brand');
        if (brand && this.brandOptions.some(function (option) { return option.value === brand; })) {
          this.brand = brand;
        }
        var sort = params.get('sort');
        if (sort && LATIN_SORTS.indexOf(sort) !== -1) this.sort = sort;
        if (this.mode === 'index') {
          var category = params.get('category');
          if (category && this.categories.some(function (item) { return item.slug === category; })) {
            this.category = category;
          }
        }
        var page = parseInt(params.get('page'), 10);
        if (!isNaN(page) && page > 1) this.page = page;
      },

      // ----- helpers -------------------------------------------------------- //
      _calcPerPage: function () {
        var width = window.innerWidth || document.documentElement.clientWidth || 1280;
        if (width < 640) return 12;
        if (width < 1024) return 16;
        return 24;
      },

      _debounce: function (fn, delay) {
        var timer = null;
        return function () {
          var args = arguments;
          var self = this;
          if (timer) window.clearTimeout(timer);
          timer = window.setTimeout(function () {
            fn.apply(self, args);
          }, delay);
        };
      },
    };

    return component;
  }

  window.latinCatalog = latinCatalog;

  // Safety net: if Alpine never boots (e.g. CDN blocked), reveal the
  // server-rendered catalog so content is never permanently hidden.
  window.setTimeout(function () {
    var cloaked = document.querySelectorAll('[x-cloak]');
    for (var i = 0; i < cloaked.length; i++) cloaked[i].removeAttribute('x-cloak');
  }, 4000);
})();
