(function() {
    // DOM elements
    const hijriSpan = document.getElementById('pbHijri');
    const gregSpan = document.getElementById('pbGreg');
    const nextNameSpan = document.getElementById('nextPrayerName');
    const nextTimeSpan = document.getElementById('nextPrayerTime');
    const countdownSpan = document.getElementById('pbCd');

    // Helper: "HH:MM" -> Date object (today)
    function parseTimeToDate(timeStr) {
        if (!timeStr) return null;
        const [hour, minute] = timeStr.split(':').map(Number);
        if (isNaN(hour) || isNaN(minute)) return null;
        const date = new Date();
        date.setHours(hour, minute, 0, 0);
        return date;
    }

    // Build prayer list from Django-injected prayerTimes
    function getPrayerList() {
        if (typeof prayerTimes === 'undefined') return [];
        const ordered = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha'];
        const prayers = [];
        for (let name of ordered) {
            let timeStr = prayerTimes[name.toLowerCase()] || prayerTimes[name];
            if (timeStr) {
                const timeDate = parseTimeToDate(timeStr);
                if (timeDate) prayers.push({ name, time: timeDate });
            }
        }
        return prayers;
    }

    // Find next prayer (or tomorrow's Fajr)
    function getNextPrayer(prayers, now) {
        if (!prayers.length) return null;
        for (let p of prayers) {
            if (p.time > now) return p;
        }
        let tomorrowFajr = new Date(prayers[0].time);
        tomorrowFajr.setDate(tomorrowFajr.getDate() + 1);
        return { name: prayers[0].name, time: tomorrowFajr };
    }

    function formatCountdown(msDiff) {
        if (msDiff <= 0) return "00:00:00";
        const totalSec = Math.floor(msDiff / 1000);
        const hours = Math.floor(totalSec / 3600);
        const minutes = Math.floor((totalSec % 3600) / 60);
        const seconds = totalSec % 60;
        return `${hours.toString().padStart(2,'0')}:${minutes.toString().padStart(2,'0')}:${seconds.toString().padStart(2,'0')}`;
    }

    function formatTime12(date) {
        return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true });
    }

    function updatePrayerUI() {
        const prayers = getPrayerList();
        if (!prayers.length) {
            nextNameSpan.innerText = '--';
            nextTimeSpan.innerText = '--:-- --';
            countdownSpan.innerText = '--:--:--';
            return;
        }
        const now = new Date();
        const next = getNextPrayer(prayers, now);
        if (next) {
            nextNameSpan.innerText = next.name;
            nextTimeSpan.innerText = formatTime12(next.time);
            const diff = next.time - now;
            countdownSpan.innerText = diff > 0 ? formatCountdown(diff) : "00:00:00";
        }
    }

    // Hijri + Gregorian via AlAdhan API
    async function loadHijriAndGregorian() {
        try {
            const today = new Date();
            const yyyy = today.getFullYear();
            const mm = String(today.getMonth() + 1).padStart(2,'0');
            const dd = String(today.getDate()).padStart(2,'0');
            const res = await fetch(`https://api.aladhan.com/v1/gToH/${yyyy}-${mm}-${dd}`);
            const data = await res.json();
            if (data?.code === 200 && data.data) {
                const h = data.data.hijri;
                hijriSpan.innerText = `${h.day} ${h.month.en} ${h.year} AH`;
            } else {
                hijriSpan.innerText = "Hijri date";
            }
        } catch(e) {
            hijriSpan.innerText = "Hijri date";
        }
        const options = { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' };
        gregSpan.innerText = new Date().toLocaleDateString(undefined, options);
    }

    // Start countdown & refresh UI every second
    let interval;
    function startCountdown() {
        updatePrayerUI();
        if (interval) clearInterval(interval);
        interval = setInterval(updatePrayerUI, 1000);
    }

    function init() {
        loadHijriAndGregorian();
        startCountdown();
        // Refresh Hijri date once per day
        const now = new Date();
        const msToMidnight = new Date(now.getFullYear(), now.getMonth(), now.getDate()+1, 0,0,0) - now;
        setTimeout(() => {
            loadHijriAndGregorian();
            setInterval(loadHijriAndGregorian, 24*60*60*1000);
        }, msToMidnight);
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();