// static/dashboards/js/dashboard.js

document.addEventListener('DOMContentLoaded', function() {

    // ====== SIDEBAR TOGGLE (already in base template) ======
    // But we also want to close it when clicking a link on mobile
    const sidebar = document.getElementById('dashSidebar');
    const links = sidebar ? sidebar.querySelectorAll('a') : [];

    links.forEach(link => {
        link.addEventListener('click', function() {
            if (window.innerWidth <= 768) {
                sidebar.classList.remove('open');
            }
        });
    });

    // ====== STATS COUNTER ANIMATION ======
    function animateCounters() {
        const counters = document.querySelectorAll('.stat-mini .number');
        counters.forEach(counter => {
            const target = parseInt(counter.textContent.replace(/,/g, ''));
            if (isNaN(target) || target === 0) return;
            const duration = 1000;
            const step = Math.max(1, Math.floor(target / 30));
            let current = 0;
            const interval = setInterval(() => {
                current += step;
                if (current >= target) {
                    current = target;
                    clearInterval(interval);
                }
                counter.textContent = current;
            }, duration / 30);
        });
    }

    // Only animate if element is visible
    const statsRow = document.querySelector('.stats-row');
    if (statsRow) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    animateCounters();
                    observer.disconnect();
                }
            });
        }, { threshold: 0.3 });
        observer.observe(statsRow);
    }

    // ====== TOOLTIP FOR PERMISSION CHECKBOXES ======
    const checkboxes = document.querySelectorAll('.permission-checkbox input[type="checkbox"]');
    checkboxes.forEach(cb => {
        cb.addEventListener('change', function() {
            const label = this.closest('.permission-checkbox');
            if (this.checked) {
                label.style.color = 'var(--gold)';
            } else {
                label.style.color = '';
            }
        });
    });

    // ====== OFFICE SWITCHER AUTO-SUBMIT ======
    const switcher = document.getElementById('switcherForm');
    if (switcher) {
        const select = switcher.querySelector('select');
        if (select) {
            select.addEventListener('change', function() {
                this.form.submit();
            });
        }
    }

    console.log('✅ NAMETS Dashboard initialized');
});