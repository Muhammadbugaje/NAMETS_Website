document.addEventListener('DOMContentLoaded', function () {
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (prefersReduced) return;

  /* ── Scroll-reveal for cards (extends existing stagger-children) ── */
  const revealEls = document.querySelectorAll('.card-reveal, .card-reveal-s');
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('animated');
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15 });
  revealEls.forEach(el => {
    el.classList.add('animate-on-scroll');
    revealObserver.observe(el);
  });

  /* ── Ambient glow pulse: random card, random interval ────
     Scoped to visible glass-card / card-reveal elements only.
     Fires roughly every 4-9 seconds, picks ONE random visible
     card, pulses it once. Never more than one at a time. */
  function pulseRandomCard() {
    const candidates = Array.from(
      document.querySelectorAll('.glass-card, .card-reveal, .card-reveal-s')
    ).filter(el => {
      const rect = el.getBoundingClientRect();
      return rect.top < window.innerHeight && rect.bottom > 0;
    });

    if (candidates.length) {
      const target = candidates[Math.floor(Math.random() * candidates.length)];
      target.classList.add('glow-pulse-active');
      setTimeout(() => target.classList.remove('glow-pulse-active'), 2200);
    }

    const nextDelay = 4000 + Math.random() * 5000; // 4-9s
    setTimeout(pulseRandomCard, nextDelay);
  }
  setTimeout(pulseRandomCard, 4000);

  /* ── Events-only ambient shine sweep ─────────────────────
     Separate from the glow pulse above. Fires on a longer,
     slower interval, ONLY on event cards. */
  function autoShineEvent() {
    const eventCards = Array.from(document.querySelectorAll('[data-ambient-card]'))
      .filter(el => {
        const rect = el.getBoundingClientRect();
        return rect.top < window.innerHeight && rect.bottom > 0;
      });

    if (eventCards.length) {
      const target = eventCards[Math.floor(Math.random() * eventCards.length)];
      target.classList.add('auto-shine');
      setTimeout(() => target.classList.remove('auto-shine'), 1200);
    }

    const nextDelay = 7000 + Math.random() * 6000; // 7-13s
    setTimeout(autoShineEvent, nextDelay);
  }
  setTimeout(autoShineEvent, 5000);
});