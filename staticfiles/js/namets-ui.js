// ========== PRAYER COUNTDOWN ==========
function initPrayerCountdown() {
    const countdownEl = document.getElementById('prayerCountdown');
    const nextPrayerNameEl = document.getElementById('nextPrayerName');
    if (!countdownEl || !nextPrayerNameEl) return;

    // Get prayer times from the JSON script tag
    let prayerTimes = {};
    const dataScript = document.getElementById('prayer-times-data');
    if (dataScript && dataScript.textContent) {
        try {
            prayerTimes = JSON.parse(dataScript.textContent);
        } catch(e) { console.warn(e); }
    }
    if (Object.keys(prayerTimes).length === 0) return;

    const order = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha'];

    function getNextPrayerIndex(now) {
        const nowMinutes = now.getHours() * 60 + now.getMinutes();
        for (let i = 0; i < order.length; i++) {
            const [h, m] = prayerTimes[order[i]].split(':').map(Number);
            const prayerMinutes = h * 60 + m;
            if (nowMinutes < prayerMinutes) return i;
        }
        return 0; // next is tomorrow's Fajr
    }

    function updateCountdown() {
        const now = new Date();
        const nextIdx = getNextPrayerIndex(now);
        const nextName = order[nextIdx];
        const nextTimeStr = prayerTimes[nextName];
        if (!nextTimeStr) return;

        // Update prayer name in the slip (optional)
        nextPrayerNameEl.textContent = nextName;

        // Compute diff to next prayer
        const [nh, nm] = nextTimeStr.split(':').map(Number);
        const nextDate = new Date(now);
        nextDate.setHours(nh, nm, 0, 0);
        if (nextDate <= now) nextDate.setDate(nextDate.getDate() + 1);
        const diff = nextDate - now;
        if (diff <= 0) {
            countdownEl.textContent = 'Now in progress';
        } else {
            const hours = Math.floor(diff / 3600000);
            const minutes = Math.floor((diff % 3600000) / 60000);
            const seconds = Math.floor((diff % 60000) / 1000);
            countdownEl.textContent = `${hours}h ${minutes}m ${seconds}s`;
        }
    }

    updateCountdown();
    setInterval(updateCountdown, 1000);
}

// Hijri date (as before)
function loadHijriDate() {
    const hijriEl = document.getElementById('hijri-date');
    if (!hijriEl) return;
    if (typeof HijriJS === 'undefined') {
        setTimeout(loadHijriDate, 100);
        return;
    }
    const today = new Date();
    const hijri = HijriJS.gregorianToHijri(today);
    const monthNames = [
        'Muharram', 'Safar', "Rabi' al-Awwal", "Rabi' al-Thani",
        'Jumada al-Ula', 'Jumada al-Thani', 'Rajab', "Sha'ban",
        'Ramadan', 'Shawwal', 'Dhu al-Qi`dah', 'Dhu al-Hijjah'
    ];
    hijriEl.textContent = `🕌 ${hijri.hd} ${monthNames[hijri.hm-1]} ${hijri.hy} AH`;
}

function initHijriLibrary() {
    if (typeof HijriJS !== 'undefined') {
        loadHijriDate();
    } else {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/hijri-js@1.0.0/dist/hijri.min.js';
        script.onload = loadHijriDate;
        document.head.appendChild(script);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initHijriLibrary();
    initPrayerCountdown();
});