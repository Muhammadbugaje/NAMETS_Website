/**
 * GLOBAL INTERACTIONS
 * - Intersection Observer for scroll animations
 * - (Optional) Mobile tap feedback enhancer
 */

(function() {
    'use strict';

    // ---------- Scroll Animations ----------
    function initScrollAnimations() {
        const elements = document.querySelectorAll('.animate-on-scroll');
        if (elements.length === 0) return;

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animated');
                    // Optional: unobserve after animation to save resources
                    observer.unobserve(entry.target);
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '0px 0px -30px 0px' // trigger a bit before element enters
        });

        elements.forEach(el => observer.observe(el));
    }

    // ---------- Mobile Active State Enhancement (optional) ----------
    // For elements that use :active but you want a longer visual feedback,
    // you can add a class on touchstart and remove it on touchend.
    // This is optional and may not be needed.
    function initTapFeedback() {
        const tapElements = document.querySelectorAll('.tap-feedback');
        if (tapElements.length === 0) return;

        tapElements.forEach(el => {
            el.addEventListener('touchstart', function() {
                this.classList.add('tapped');
            });
            el.addEventListener('touchend', function() {
                this.classList.remove('tapped');
            });
            el.addEventListener('touchcancel', function() {
                this.classList.remove('tapped');
            });
        });
    }

    // Run on DOM ready
    document.addEventListener('DOMContentLoaded', function() {
        initScrollAnimations();
        initTapFeedback(); // remove if not needed
    });
})();


(function() {
    document.addEventListener('DOMContentLoaded', function() {
        var overlay  = document.getElementById('drawer-overlay');
        var drawer   = document.getElementById('drawer');
        var openBtn  = document.getElementById('drawer-open-btn');
        var closeBtn = document.getElementById('drawer-close-btn');

        // Exit if drawer elements don't exist on this page
        if (!overlay || !drawer || !openBtn || !closeBtn) return;

        function open() {
      overlay.classList.add('open');
      drawer.classList.add('open');
      overlay.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
      openBtn.setAttribute('aria-expanded', 'true');
      closeBtn.focus();
    }

    function close() {
      overlay.classList.remove('open');
      drawer.classList.remove('open');
      overlay.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = '';
      openBtn.setAttribute('aria-expanded', 'false');
      openBtn.focus();
    }

    openBtn.addEventListener('click', open);
    closeBtn.addEventListener('click', close);
    overlay.addEventListener('click', close);

    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape' && drawer.classList.contains('open')) {
        close();
      }
    });

    // Trap focus inside drawer
    drawer.addEventListener('keydown', function(e) {
      if (e.key !== 'Tab') return;
      var focusable = drawer.querySelectorAll('a[href], button, [tabindex]:not([tabindex="-1"])');
      if (focusable.length === 0) return;
      var first = focusable[0];
      var last  = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    });

          // Mark active link in drawer (simple)
          var links = document.querySelectorAll('#drawer-nav a');
          var path  = window.location.pathname;
          links.forEach(function(link) {
            if (link.getAttribute('href') === path) {
              link.classList.add('active');
            }
          });
      });
  })();


/**
 * Mobile Menu Controller
 * Handles opening/closing, focus trap, and ESC key
 */
(function() {
    'use strict';

    const body = document.body;
    const overlay = document.getElementById('drawer-overlay');
    const drawer = document.getElementById('drawer');
    const openBtn = document.getElementById('drawer-open-btn');
    const closeBtn = document.getElementById('drawer-close-btn');

    if (!overlay || !drawer || !openBtn || !closeBtn) return;

    // Get all focusable elements inside the drawer (for focus trap)
    const focusableElements = drawer.querySelectorAll('a[href], button, [tabindex]:not([tabindex="-1"])');
    const firstFocusable = focusableElements[0];
    const lastFocusable = focusableElements[focusableElements.length - 1];

    function openMenu() {
        body.classList.add('menu-open');
        overlay.setAttribute('aria-hidden', 'false');
        drawer.setAttribute('aria-hidden', 'false');
        openBtn.setAttribute('aria-expanded', 'true');
        closeBtn.focus(); // move focus to close button
    }

    function closeMenu() {
        body.classList.remove('menu-open');
        overlay.setAttribute('aria-hidden', 'true');
        drawer.setAttribute('aria-hidden', 'true');
        openBtn.setAttribute('aria-expanded', 'false');
        openBtn.focus();
    }

    // Event listeners
    openBtn.addEventListener('click', openMenu);
    closeBtn.addEventListener('click', closeMenu);
    overlay.addEventListener('click', closeMenu);

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && body.classList.contains('menu-open')) {
            closeMenu();
        }
    });

    // Focus trap inside drawer
    drawer.addEventListener('keydown', (e) => {
        if (e.key !== 'Tab') return;
        if (e.shiftKey) {
            if (document.activeElement === firstFocusable) {
                e.preventDefault();
                lastFocusable.focus();
            }
        } else {
            if (document.activeElement === lastFocusable) {
                e.preventDefault();
                firstFocusable.focus();
            }
        }
    });

    // Ensure that when menu closes, focus is returned to open button (already done)
})();

