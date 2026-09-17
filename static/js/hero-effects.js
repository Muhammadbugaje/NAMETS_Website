document.addEventListener('DOMContentLoaded', function () {
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── Rotating hero subtitle phrases ─────────────────────── */
  const phrases = document.querySelectorAll('#heroRotator .hero-phrase');
  if (phrases.length > 1 && !prefersReduced) {
    let current = 0;
    setInterval(() => {
      phrases[current].classList.remove('active');
      current = (current + 1) % phrases.length;
      phrases[current].classList.add('active');
    }, 3200);
  }

  /* ── Scroll cue: vanish on scroll, intensify on inactivity ── */
  const scrollCue = document.getElementById('scrollCue');
  if (scrollCue) {
    let hasScrolled = false;
    let inactivityTimer;

    window.addEventListener('scroll', () => {
      if (window.scrollY > 80 && !hasScrolled) {
        hasScrolled = true;
        scrollCue.classList.add('hidden');
      }
    }, { passive: true });

    scrollCue.addEventListener('click', () => {
      window.scrollTo({ top: window.innerHeight * 0.85, behavior: 'smooth' });
    });

    // Nudge (not auto-scroll) after 6s of no scroll activity
    if (!prefersReduced) {
      inactivityTimer = setTimeout(() => {
        if (!hasScrolled) scrollCue.classList.add('nudge');
      }, 6000);
    }
  }
});