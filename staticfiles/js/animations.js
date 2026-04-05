/**
 * NAMETS Advanced Animations
 * - Shimmer (desktop hover on glass elements)
 * - Scroll progress bar
 * - Ripple click effect
 * - GSAP: hero entrance, card stagger, reveal animations
 * - Touch feedback for mobile
 * - Dynamic navbar colour based on section background
 */

(function () {
  'use strict';

  /* =========================================================
     1. Shimmer – tracks cursor position on glass elements
     ========================================================= */
  function initShimmer() {
    const els = document.querySelectorAll('.glass-card, .glass');
    els.forEach(el => {
      el.addEventListener('mousemove', (e) => {
        const r = el.getBoundingClientRect();
        el.style.setProperty('--shimmer-x', `${e.clientX - r.left}px`);
        el.style.setProperty('--shimmer-y', `${e.clientY - r.top}px`);
      });
    });
  }

  /* =========================================================
     2. Scroll Progress Bar
     ========================================================= */
  function initScrollProgress() {
    const bar = document.getElementById('scroll-progress');
    if (!bar) return;
    const update = () => {
      const docH = document.documentElement.scrollHeight - window.innerHeight;
      bar.style.width = docH > 0 ? `${(window.scrollY / docH) * 100}%` : '0%';
    };
    window.addEventListener('scroll', update, { passive: true });
    update(); // initial call
  }

  /* =========================================================
     3. Ripple – click effect on buttons, glass cards, tabs
     ========================================================= */
  function initRipple() {
    document.querySelectorAll('.btn, .glass-card, .filter-tab').forEach(el => {
      // ensure container clips the ripple circle
      const cs = window.getComputedStyle(el);
      if (cs.position === 'static') el.style.position = 'relative';
      if (cs.overflow !== 'hidden') el.style.overflow = 'hidden';

      el.addEventListener('click', function (e) {
        const r = this.getBoundingClientRect();
        const size = Math.max(r.width, r.height) * 2;
        const rpl = document.createElement('span');
        Object.assign(rpl.style, {
          position: 'absolute',
          width: `${size}px`,
          height: `${size}px`,
          left: `${e.clientX - r.left - size / 2}px`,
          top: `${e.clientY - r.top - size / 2}px`,
          borderRadius: '50%',
          background: 'rgba(255,255,255,0.28)',
          transform: 'scale(0)',
          animation: 'ripple-anim 0.65s linear forwards',
          pointerEvents: 'none',
        });
        this.appendChild(rpl);
        setTimeout(() => rpl.remove(), 750);
      });
    });
  }

  /* =========================================================
     4. GSAP Animations (hero, stagger, reveal)
     ========================================================= */
  function initGSAP() {
    if (typeof gsap === 'undefined') return;
    gsap.registerPlugin(ScrollTrigger);

    // --- Hero entrance ---
    const heroTitle    = document.querySelector('.hero-title');
    const heroSubtitle = document.querySelector('.hero-subtitle');
    const heroActions  = document.querySelector('.hero-actions');
    const heroGeo      = document.querySelectorAll('.hero-geo, .hero-geo-2');

    if (heroTitle) {
      const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });
      tl.from(heroGeo,      { scale: 0, opacity: 0, duration: 1.2, stagger: 0.2 })
        .from(heroTitle,    { y: 55, opacity: 0, duration: 0.85 }, '-=0.9')
        .from(heroSubtitle, { y: 30, opacity: 0, duration: 0.7  }, '-=0.55')
        .from(heroActions,  { y: 20, opacity: 0, duration: 0.6  }, '-=0.45');
    }

    // --- Card grid stagger (skip if child of a grid handled separately) ---
    document.querySelectorAll('.card-grid').forEach(grid => {
      const children = Array.from(grid.children);
      if (!children.length) return;
      gsap.from(children, {
        scrollTrigger: { trigger: grid, start: 'top 88%' },
        y: 40,
        opacity: 0,
        duration: 0.55,
        stagger: 0.13,
        ease: 'power2.out',
        clearProps: 'all',
      });
    });

    // --- .card-reveal (standalone elements outside .card-grid) ---
    gsap.utils.toArray('.card-reveal').forEach(el => {
      if (el.closest('.card-grid')) return; // already handled
      gsap.from(el, {
        scrollTrigger: {
          trigger: el,
          start: 'top 87%',
          toggleActions: 'play none none reverse',
        },
        y: 35,
        scale: 0.96,
        opacity: 0.8,
        duration: 0.5,
        ease: 'power2.out',
      });
    });

    // --- .card-reveal-s (slower/fainter) ---
    gsap.utils.toArray('.card-reveal-s').forEach(el => {
      gsap.from(el, {
        scrollTrigger: {
          trigger: el,
          start: 'top 87%',
          toggleActions: 'play none none reverse',
        },
        y: 20,
        opacity: 0.8,
        duration: 0.35,
        ease: 'power1.out',
      });
    });

    // --- .reveal headings (skip hero children) ---
    gsap.utils.toArray('.reveal').forEach(el => {
      if (el.closest('.hero-section')) return;
      gsap.from(el, {
        scrollTrigger: {
          trigger: el,
          start: 'top 83%',
          toggleActions: 'play none none reverse',
        },
        opacity: 0,
        y: 28,
        duration: 0.65,
        ease: 'power2.out',
      });
    });

    // --- Section heading lines animate width ---
    gsap.utils.toArray('.section-heading-line').forEach(line => {
      gsap.from(line, {
        scrollTrigger: { trigger: line, start: 'top 90%' },
        scaleX: 0,
        transformOrigin: 'left center',
        duration: 0.7,
        ease: 'power2.out',
      });
    });
  }

  /* =========================================================
     5. Touch Feedback – mobile press state on cards
     ========================================================= */
  function initTouchFeedback() {
    if (!window.matchMedia('(hover: none)').matches) return;

    document.querySelectorAll('.glass-card, .card, .item-card').forEach(el => {
      el.addEventListener('touchstart', () => {
        el.classList.add('card-touch-active');
      }, { passive: true });
      const release = () => el.classList.remove('card-touch-active');
      el.addEventListener('touchend',   release, { passive: true });
      el.addEventListener('touchcancel', release, { passive: true });
    });
  }

  /* =========================================================
     6. Dynamic Navbar colour (light text over dark sections)
     ========================================================= */
  function initNavbarColor() {
    const navbar = document.querySelector('.site-header');
    if (!navbar) return;
    const darkSections = document.querySelectorAll('[data-bg="dark"]');
    if (!darkSections.length) return;

    function check() {
      const nr = navbar.getBoundingClientRect();
      let isLight = false;
      darkSections.forEach(s => {
        const sr = s.getBoundingClientRect();
        if (sr.bottom > nr.top && sr.top < nr.bottom) isLight = true;
      });
      navbar.classList.toggle('navbar-light-text', isLight);
    }
    window.addEventListener('scroll', check, { passive: true });
    window.addEventListener('resize', check);
    check();
  }

  /* =========================================================
     Init
     ========================================================= */
  document.addEventListener('DOMContentLoaded', () => {
    initShimmer();
    initScrollProgress();
    initRipple();
    initGSAP();
    initTouchFeedback();
    initNavbarColor();
  });
})();
