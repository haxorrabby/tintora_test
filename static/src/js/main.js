/**
 * TINTORA MADRID - Client Core Script
 * Alpine.js Stores, HTMX CSRF integration, Lenis Smooth Scroll
 */

document.addEventListener('error', (event) => {
  const image = event.target;
  if (!(image instanceof HTMLImageElement) || !image.matches('[data-product-image]')) return;

  const frame = image.closest('[data-product-image-frame]');
  const fallback = frame?.querySelector('[data-product-image-fallback]');
  if (!fallback) return;

  image.hidden = true;
  image.classList.add('hidden');
  fallback.hidden = false;
  fallback.classList.remove('hidden');
}, true);

document.addEventListener('load', (event) => {
  const image = event.target;
  if (!(image instanceof HTMLImageElement) || !image.matches('[data-product-image]')) return;

  const frame = image.closest('[data-product-image-frame]');
  const fallback = frame?.querySelector('[data-product-image-fallback]');
  if (!fallback) return;

  image.hidden = false;
  image.classList.remove('hidden');
  fallback.hidden = true;
  fallback.classList.add('hidden');
}, true);

document.addEventListener('DOMContentLoaded', () => {
  // 1. Lenis Smooth Scroll Initialization (respects prefers-reduced-motion)
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!prefersReducedMotion && typeof Lenis !== 'undefined') {
    const lenis = new Lenis({
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      orientation: 'vertical',
      gestureOrientation: 'vertical',
      smoothWheel: true,
      wheelMultiplier: 1.0,
      touchMultiplier: 2.0,
    });

    function raf(time) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }
    requestAnimationFrame(raf);
    window.tintoraLenis = lenis;
  }

  // 2. Configure HTMX with Django CSRF Token
  if (typeof htmx !== 'undefined') {
    document.body.addEventListener('htmx:configRequest', (event) => {
      const getCookie = (name) => {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
          const cookies = document.cookie.split(';');
          for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
              cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
              break;
            }
          }
        }
        return cookieValue;
      };
      const csrfToken = getCookie('csrftoken');
      if (csrfToken) {
        event.detail.headers['X-CSRFToken'] = csrfToken;
      }
    });
  }
});

// 3. Alpine.js Stores Initialization
document.addEventListener('alpine:init', () => {
  // Theme Manager (Dark / Light)
  Alpine.store('theme', {
    dark: localStorage.getItem('tintora_theme') === 'dark' || 
          (!('tintora_theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches),

    init() {
      this.apply();
    },

    toggle() {
      this.dark = !this.dark;
      localStorage.setItem('tintora_theme', this.dark ? 'dark' : 'light');
      this.apply();
    },

    apply() {
      if (this.dark) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    }
  });

  // Mega Menu State
  Alpine.store('nav', {
    megaMenuOpen: false,
    activeTab: 'print',
    mobileMenuOpen: false,

    openMega(tab = 'print') {
      this.activeTab = tab;
      this.megaMenuOpen = true;
    },
    closeMega() {
      this.megaMenuOpen = false;
    },
    toggleMobile() {
      this.mobileMenuOpen = !this.mobileMenuOpen;
    }
  });

  // Cookie Consent Store (GDPR Compliant for Spain/EU)
  Alpine.store('cookies', {
    bannerVisible: !localStorage.getItem('tintora_cookie_consent'),
    preferences: JSON.parse(localStorage.getItem('tintora_cookie_prefs') || '{"necessary": true, "analytics": false, "marketing": false}'),
    modalOpen: false,

    acceptAll() {
      this.preferences = { necessary: true, analytics: true, marketing: true };
      this.saveConsent('all');
    },

    acceptNecessary() {
      this.preferences = { necessary: true, analytics: false, marketing: false };
      this.saveConsent('necessary');
    },

    saveCustom() {
      this.saveConsent('custom');
      this.modalOpen = false;
    },

    saveConsent(type) {
      localStorage.setItem('tintora_cookie_consent', type);
      localStorage.setItem('tintora_cookie_prefs', JSON.stringify(this.preferences));
      this.bannerVisible = false;
    }
  });
});
