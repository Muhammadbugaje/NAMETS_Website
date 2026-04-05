(function() {
    // ----- DOM elements -----
    const hijriSpan = document.getElementById('pbHijri');
    const gregSpan = document.getElementById('pbGreg');
    const nextNameSpan = document.getElementById('nextPrayerName');
    const nextTimeSpan = document.getElementById('nextPrayerTime');
    const countdownSpan = document.getElementById('pbCd');
    const labelSpan = document.getElementById('pbLbl');

    // ----- Helper: "HH:MM" -> Date object (today) -----
    function parseTimeToDate(timeStr) {
        if (!timeStr) return null;
        const [hour, minute] = timeStr.split(':').map(Number);
        if (isNaN(hour) || isNaN(minute)) return null;
        const date = new Date();
        date.setHours(hour, minute, 0, 0);
        return date;
    }

    // ----- Get today's prayer list from global prayerTimes -----
    function getPrayerList() {
        if (typeof prayerTimes === 'undefined' || !prayerTimes) return [];
        const ordered = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha'];
        const prayers = [];
        for (let name of ordered) {
            let timeStr = prayerTimes[name];
            if (timeStr) {
                const timeDate = parseTimeToDate(timeStr);
                if (timeDate) prayers.push({ name, time: timeDate });
            }
        }
        return prayers;
    }

    // ----- Determine current prayer status -----
    // Returns: { status, prayer, timeLeftMs, label }
    // status: 'ongoing' | 'upcoming'
    function getPrayerStatus(now, prayers) {
        if (!prayers.length) return null;

        // Check for ongoing prayer (within 30 minutes after its time)
        for (let p of prayers) {
            const endTime = new Date(p.time.getTime() + 30 * 60000);
            if (now >= p.time && now <= endTime) {
                const timeLeftMs = endTime - now;
                return {
                    status: 'ongoing',
                    prayer: p,
                    timeLeftMs: timeLeftMs,
                    label: 'ends in'
                };
            }
        }

        // No ongoing: find next prayer (including tomorrow's Fajr if all passed)
        for (let p of prayers) {
            if (p.time > now) {
                return {
                    status: 'upcoming',
                    prayer: p,
                    timeLeftMs: p.time - now,
                    label: 'in'
                };
            }
        }
        // All prayers passed for today → next is tomorrow's Fajr
        let tomorrowFajr = new Date(prayers[0].time);
        tomorrowFajr.setDate(tomorrowFajr.getDate() + 1);
        return {
            status: 'upcoming',
            prayer: { name: prayers[0].name, time: tomorrowFajr },
            timeLeftMs: tomorrowFajr - now,
            label: 'in'
        };
    }

    // ----- Format milliseconds to HH:MM:SS -----
    function formatCountdown(ms) {
        if (ms <= 0) return "00:00:00";
        const totalSec = Math.floor(ms / 1000);
        const hours = Math.floor(totalSec / 3600);
        const minutes = Math.floor((totalSec % 3600) / 60);
        const seconds = totalSec % 60;
        return `${hours.toString().padStart(2,'0')}:${minutes.toString().padStart(2,'0')}:${seconds.toString().padStart(2,'0')}`;
    }

    // ----- Format time to 12h (e.g., "6:30 PM") -----
    function formatTime12(date) {
        return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true });
    }

    // ----- Main update function (called every second) -----
    function updatePrayerUI() {
        const prayers = getPrayerList();
        if (!prayers.length) {
            if (nextNameSpan) nextNameSpan.innerText = '--';
            if (nextTimeSpan) nextTimeSpan.innerText = '--:--';
            if (countdownSpan) countdownSpan.innerText = '--:--:--';
            if (labelSpan) labelSpan.innerText = 'in';
            return;
        }

        const now = new Date();
        const status = getPrayerStatus(now, prayers);
        if (!status) return;

        const prayer = status.prayer;
        // Update centre section
        nextNameSpan.innerText = prayer.name;
        nextTimeSpan.innerText = formatTime12(prayer.time);
        
        // Update right section
        if (status.status === 'ongoing') {
            labelSpan.innerText = 'ends in';
            countdownSpan.innerText = formatCountdown(status.timeLeftMs);
        } else {
            labelSpan.innerText = 'in';
            countdownSpan.innerText = formatCountdown(status.timeLeftMs);
        }
    }

    // ----- Hijri date (AlAdhan API) with correct DD-MM-YYYY -----
    async function loadHijriAndGregorian() {
        try {
            const today = new Date();
            const dd = String(today.getDate()).padStart(2, '0');
            const mm = String(today.getMonth() + 1).padStart(2, '0');
            const yyyy = today.getFullYear();
            const res = await fetch(`https://api.aladhan.com/v1/gToH/${dd}-${mm}-${yyyy}`);
            const data = await res.json();
            if (data?.code === 200 && data.data) {
                const h = data.data.hijri;
                if (hijriSpan) hijriSpan.innerText = `${h.day} ${h.month.en} ${h.year} AH`;
                else hijriSpan.innerText = "Hijri";
            } else {
                if (hijriSpan) hijriSpan.innerText = "Hijri date";
            }
        } catch(e) {
            if (hijriSpan) hijriSpan.innerText = "Hijri";
        }
        if (gregSpan) {
            const options = { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' };
            gregSpan.innerText = new Date().toLocaleDateString(undefined, options);
        }
    }

    // ----- Start everything -----
    function init() {
        // Initial updates
        updatePrayerUI();
        loadHijriAndGregorian();
        
        // Refresh countdown every second
        setInterval(updatePrayerUI, 1000);
        
        // Refresh Hijri date once per day
        const now = new Date();
        const msToMidnight = new Date(now.getFullYear(), now.getMonth(), now.getDate()+1, 0,0,0) - now;
        setTimeout(() => {
            loadHijriAndGregorian();
            setInterval(loadHijriAndGregorian, 24*60*60*1000);
        }, msToMidnight);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();