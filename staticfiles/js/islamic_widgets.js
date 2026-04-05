/**
 * ═══════════════════════════════════════════════════════════════════════════
 *  NAMETS Islamic Widgets — islamic_widgets.js
 *  File: static/js/islamic_widgets.js
 *
 *  Add to base.html BEFORE </body>:
 *    <script src="{% static 'js/islamic_widgets.js' %}"></script>
 *
 *  Features:
 *    1. Prayer bar: live countdown to next prayer, "In Progress" detection
 *    2. Hijri calendar from AlAdhan API
 *    3. Context-aware Quran verse + Hadith section
 *       - Friday → Surah Al-Kahf reminder + Friday hadith
 *       - Ramadan (Hijri month 9) → fasting verses + Ramadan hadith
 *       - Eid al-Fitr / Eid al-Adha → Eid content
 *       - Default → rotating daily verse + hadith
 *
 *  APIs used (free, no auth key needed):
 *    • https://api.aladhan.com  — prayer times + Hijri date
 *    • https://api.alquran.cloud — Arabic verse + English translation
 * ═══════════════════════════════════════════════════════════════════════════
 */

;(function () {
  'use strict';

  /* ── Configuration ────────────────────────────────────────────────────── */
  const CONFIG = {
    // Ahmadu Bello University, Zaria
    lat:     11.1564,
    lng:      7.7206,
    city:   'Zaria',
    country: 'Nigeria',
    method:  3,          // Muslim World League (used widely in Nigeria)
    // Duration (minutes) a prayer is considered "in progress" after its adhan
    inProgressMinutes: 20,
  };

  /* ── Curated Content Library ──────────────────────────────────────────── */

  // Each entry: { surah, ayah, arabic, translation, reference }
  const DAILY_VERSES = [
    {
      surah: 20, ayah: 114,
      arabic: 'وَقُل رَّبِّ زِدْنِي عِلْمًا',
      translation: '"And say: My Lord, increase me in knowledge."',
      reference: 'Surah Ta-Ha, 20:114'
    },
    {
      surah: 2, ayah: 286,
      arabic: 'لَا يُكَلِّفُ اللَّهُ نَفْسًا إِلَّا وُسْعَهَا',
      translation: '"Allah does not burden a soul beyond that it can bear."',
      reference: 'Surah Al-Baqarah, 2:286'
    },
    {
      surah: 13, ayah: 11,
      arabic: 'إِنَّ اللَّهَ لَا يُغَيِّرُ مَا بِقَوْمٍ حَتَّى يُغَيِّرُوا مَا بِأَنفُسِهِمْ',
      translation: '"Indeed, Allah will not change the condition of a people until they change what is in themselves."',
      reference: 'Surah Ar-Ra\'d, 13:11'
    },
    {
      surah: 94, ayah: 5,
      arabic: 'فَإِنَّ مَعَ الْعُسْرِ يُسْرًا',
      translation: '"For indeed, with hardship will be ease."',
      reference: 'Surah Ash-Sharh, 94:5'
    },
    {
      surah: 39, ayah: 53,
      arabic: 'لَا تَقْنَطُوا مِن رَّحْمَةِ اللَّهِ ۚ إِنَّ اللَّهَ يَغْفِرُ الذُّنُوبَ جَمِيعًا',
      translation: '"Do not despair of the mercy of Allah. Indeed, Allah forgives all sins."',
      reference: 'Surah Az-Zumar, 39:53'
    },
    {
      surah: 2, ayah: 153,
      arabic: 'يَا أَيُّهَا الَّذِينَ آمَنُوا اسْتَعِينُوا بِالصَّبْرِ وَالصَّلَاةِ',
      translation: '"O you who have believed, seek help through patience and prayer."',
      reference: 'Surah Al-Baqarah, 2:153'
    },
    {
      surah: 3, ayah: 139,
      arabic: 'وَلَا تَهِنُوا وَلَا تَحْزَنُوا وَأَنتُمُ الْأَعْلَوْنَ إِن كُنتُم مُّؤْمِنِينَ',
      translation: '"Do not weaken and do not grieve, and you will be superior if you are believers."',
      reference: 'Surah Ali \'Imran, 3:139'
    },
  ];

  const DAILY_HADITHS = [
    {
      arabic: 'طَلَبُ الْعِلْمِ فَرِيضَةٌ عَلَى كُلِّ مُسْلِمٍ',
      text: '"Seeking knowledge is an obligation upon every Muslim."',
      source: 'Ibn Majah, 224 — Sahih'
    },
    {
      arabic: 'إِنَّمَا الأَعْمَالُ بِالنِّيَّاتِ',
      text: '"Verily, actions are judged by intentions."',
      source: 'Bukhari, 1 — Sahih'
    },
    {
      arabic: 'الْمُسْلِمُ مَنْ سَلِمَ الْمُسْلِمُونَ مِنْ لِسَانِهِ وَيَدِهِ',
      text: '"A Muslim is one from whose tongue and hand other Muslims are safe."',
      source: 'Bukhari, 10 — Sahih'
    },
    {
      arabic: 'لَا يُؤْمِنُ أَحَدُكُمْ حَتَّى يُحِبَّ لِأَخِيهِ مَا يُحِبُّ لِنَفْسِهِ',
      text: '"None of you truly believes until he loves for his brother what he loves for himself."',
      source: 'Bukhari, 13 — Sahih'
    },
    {
      arabic: 'مَنْ سَلَكَ طَرِيقًا يَلْتَمِسُ فِيهِ عِلْمًا سَهَّلَ اللَّهُ لَهُ طَرِيقًا إِلَى الْجَنَّةِ',
      text: '"Whoever takes a path seeking knowledge, Allah will make easy for him a path to Paradise."',
      source: 'Muslim, 2699 — Sahih'
    },
  ];

  // Friday-specific content (Surah Al-Kahf ayahs)
  const FRIDAY_VERSES = [
    {
      arabic: 'الْحَمْدُ لِلَّهِ الَّذِي أَنزَلَ عَلَىٰ عَبْدِهِ الْكِتَابَ وَلَمْ يَجْعَل لَّهُ عِوَجًا',
      translation: '"Praise be to Allah, who has sent down upon His Servant the Book and has not made therein any crookedness."',
      reference: 'Surah Al-Kahf, 18:1 — Jumu\'ah Verse'
    },
    {
      arabic: 'وَاصْبِرْ نَفْسَكَ مَعَ الَّذِينَ يَدْعُونَ رَبَّهُم بِالْغَدَاةِ وَالْعَشِيِّ يُرِيدُونَ وَجْهَهُ',
      translation: '"And keep yourself patient with those who call upon their Lord in the morning and the evening, seeking His face."',
      reference: 'Surah Al-Kahf, 18:28 — Jumu\'ah Verse'
    },
    {
      arabic: 'يَوْمَ نَطْوِي السَّمَاءَ كَطَيِّ السِّجِلِّ لِلْكُتُبِ',
      translation: '"The Day when We will fold the heaven like the folding of a written sheet."',
      reference: 'Surah Al-Anbiya, 21:104 — Friday Reflection'
    },
  ];

  const FRIDAY_HADITHS = [
    {
      arabic: 'مَنْ قَرَأَ سُورَةَ الْكَهْفِ فِي يَوْمِ الْجُمُعَةِ أَضَاءَ لَهُ مِنَ النُّورِ مَا بَيْنَ الْجُمُعَتَيْنِ',
      text: '"Whoever reads Surah Al-Kahf on Friday will have a light between the two Fridays."',
      source: 'Al-Hakim, 2/368 — Sahih'
    },
    {
      arabic: 'أَكْثِرُوا الصَّلَاةَ عَلَيَّ يَوْمَ الْجُمُعَةِ',
      text: '"Send abundant salawat upon me on Friday."',
      source: 'Abu Dawud, 1047 — Sahih'
    },
    {
      arabic: 'فِي يَوْمِ الْجُمُعَةِ سَاعَةٌ لَا يُوَافِقُهَا عَبْدٌ مُسْلِمٌ وَهُوَ قَائِمٌ يُصَلِّي يَسْأَلُ اللَّهَ شَيْئًا إِلَّا أَعْطَاهُ إِيَّاهُ',
      text: '"On Friday there is a moment in which no Muslim stands in prayer asking Allah for something except that He gives it to him."',
      source: 'Bukhari, 935 — Sahih'
    },
  ];

  // Ramadan-specific content
  const RAMADAN_VERSES = [
    {
      arabic: 'شَهْرُ رَمَضَانَ الَّذِي أُنزِلَ فِيهِ الْقُرْآنُ هُدًى لِّلنَّاسِ',
      translation: '"The month of Ramadan is that in which the Quran was revealed as guidance for mankind."',
      reference: 'Surah Al-Baqarah, 2:185 — Ramadan Verse'
    },
    {
      arabic: 'وَإِذَا سَأَلَكَ عِبَادِي عَنِّي فَإِنِّي قَرِيبٌ ۖ أُجِيبُ دَعْوَةَ الدَّاعِ إِذَا دَعَانِ',
      translation: '"And when My servants ask you about Me — indeed I am near. I respond to the invocation of the supplicant when he calls upon Me."',
      reference: 'Surah Al-Baqarah, 2:186 — Ramadan Dua Verse'
    },
    {
      arabic: 'يَا أَيُّهَا الَّذِينَ آمَنُوا كُتِبَ عَلَيْكُمُ الصِّيَامُ كَمَا كُتِبَ عَلَى الَّذِينَ مِن قَبْلِكُمْ',
      translation: '"O you who believe! Fasting is prescribed upon you as it was prescribed upon those before you."',
      reference: 'Surah Al-Baqarah, 2:183 — Ramadan Verse'
    },
    {
      arabic: 'لَيْلَةُ الْقَدْرِ خَيْرٌ مِّنْ أَلْفِ شَهْرٍ',
      translation: '"The Night of Decree is better than a thousand months."',
      reference: 'Surah Al-Qadr, 97:3 — Ramadan Verse'
    },
  ];

  const RAMADAN_HADITHS = [
    {
      arabic: 'مَنْ صَامَ رَمَضَانَ إِيمَانًا وَاحْتِسَابًا غُفِرَ لَهُ مَا تَقَدَّمَ مِنْ ذَنْبِهِ',
      text: '"Whoever fasts Ramadan out of faith and seeking reward, his previous sins will be forgiven."',
      source: 'Bukhari, 38 — Sahih'
    },
    {
      arabic: 'إِذَا جَاءَ رَمَضَانُ فُتِّحَتْ أَبْوَابُ الْجَنَّةِ وَغُلِّقَتْ أَبْوَابُ النَّارِ',
      text: '"When Ramadan comes, the gates of Paradise are opened, the gates of Hellfire are closed, and the devils are chained."',
      source: 'Bukhari, 1899 — Sahih'
    },
    {
      arabic: 'الصِّيَامُ جُنَّةٌ',
      text: '"Fasting is a shield (from sin and the Hellfire)."',
      source: 'Bukhari, 1904 — Sahih'
    },
  ];

  // Eid content
  const EID_VERSES = [
    {
      arabic: 'وَلِتُكْمِلُوا الْعِدَّةَ وَلِتُكَبِّرُوا اللَّهَ عَلَى مَا هَدَاكُمْ وَلَعَلَّكُمْ تَشْكُرُونَ',
      translation: '"Complete the prescribed period and glorify Allah for having guided you, and that you may be grateful."',
      reference: 'Surah Al-Baqarah, 2:185 — Eid al-Fitr'
    },
    {
      arabic: 'فَصَلِّ لِرَبِّكَ وَانْحَرْ',
      translation: '"So pray to your Lord and sacrifice [to Him alone]."',
      reference: 'Surah Al-Kawthar, 108:2 — Eid al-Adha'
    },
  ];

  /* ── State ────────────────────────────────────────────────────────────── */
  let prayerTimes    = null;   // { Fajr, Dhuhr, Asr, Maghrib, Isha } (Date objects)
  let hijriData      = null;   // { day, month, monthName, year }
  let countdownTimer = null;
  let currentSlide   = 0;
  let slides         = [];     // array of { verse, hadith }

  /* ── Utilities ────────────────────────────────────────────────────────── */

  function pad(n) { return String(n).padStart(2, '0'); }

  function timeToDate(timeStr) {
    // timeStr like "05:12" → today's Date at that time
    const [h, m] = timeStr.split(':').map(Number);
    const d = new Date();
    d.setHours(h, m, 0, 0);
    return d;
  }

  function formatTime12(d) {
    let h = d.getHours(), m = d.getMinutes();
    const ampm = h >= 12 ? 'PM' : 'AM';
    h = h % 12 || 12;
    return `${h}:${pad(m)} ${ampm}`;
  }

  function getDayOfWeek() { return new Date().getDay(); } // 0=Sun, 5=Fri
  function isFriday()     { return getDayOfWeek() === 5; }

  /* ── Season / Context Detection ─────────────────────────────────────── */

  function getContext(hijri) {
    if (!hijri) return 'default';
    const { month, day } = hijri;
    if (month === 9)  return 'ramadan';
    if (month === 10 && day >= 1 && day <= 3)  return 'eid_fitr';
    if (month === 12 && day >= 10 && day <= 13) return 'eid_adha';
    if (isFriday())   return 'friday';
    return 'default';
  }

  /* ── Build Slide Deck ─────────────────────────────────────────────────── */

  function buildSlides(context) {
    switch (context) {
      case 'ramadan':
        return RAMADAN_VERSES.map((v, i) => ({
          verse:  v,
          hadith: RAMADAN_HADITHS[i % RAMADAN_HADITHS.length]
        }));

      case 'friday':
        return FRIDAY_VERSES.map((v, i) => ({
          verse:  v,
          hadith: FRIDAY_HADITHS[i % FRIDAY_HADITHS.length]
        }));

      case 'eid_fitr':
      case 'eid_adha':
        return EID_VERSES.map(v => ({ verse: v, hadith: null }));

      default: {
        // Rotate based on day-of-year so it changes daily
        const dayOfYear = Math.floor(
          (new Date() - new Date(new Date().getFullYear(), 0, 0)) / 86400000
        );
        const offset = dayOfYear % DAILY_VERSES.length;
        // Show 3 slides starting from today's offset
        return [0, 1, 2].map(i => ({
          verse:  DAILY_VERSES[(offset + i) % DAILY_VERSES.length],
          hadith: DAILY_HADITHS[(offset + i) % DAILY_HADITHS.length],
        }));
      }
    }
  }

  /* ── Context Banner ─────────────────────────────────────────────────── */

  function renderContextBanner(context) {
    const banner = document.getElementById('nametsContextBanner');
    const icon   = document.getElementById('nametsContextIcon');
    const text   = document.getElementById('nametsContextText');
    const eyebrow = document.getElementById('nametsQsEyebrow');
    const title   = document.getElementById('nametsQsTitle');

    const configs = {
      ramadan:  { icon:'🌙', text:'Ramadan Mubarak — Fasting Edition',    eyebrow:'Ramadan Kareem', title:'Verses of Fasting & Taqwa' },
      friday:   { icon:'🕌', text:'Jumu\'ah Mubarak — Friday Edition',   eyebrow:'Jumu\'ah Mubarak', title:'Friday Quran & Reminders' },
      eid_fitr: { icon:'🎉', text:'Eid al-Fitr Mubarak — عيد الفطر',    eyebrow:'Eid Mubarak', title:'Joy of Eid al-Fitr' },
      eid_adha: { icon:'🐑', text:'Eid al-Adha Mubarak — عيد الأضحى',  eyebrow:'Eid Mubarak', title:'The Day of Sacrifice' },
      default:  null,
    };

    const cfg = configs[context];
    if (cfg) {
      icon.textContent    = cfg.icon;
      text.textContent    = cfg.text;
      eyebrow.textContent = cfg.eyebrow;
      title.textContent   = cfg.title;
      banner.style.display = 'inline-flex';
    }

    // Friday reminder card
    const fri = document.getElementById('nametsFridayReminder');
    if (fri) fri.style.display = context === 'friday' ? 'flex' : 'none';
  }

  /* ── Render Slide ─────────────────────────────────────────────────────── */

  function renderSlide(idx) {
    if (!slides.length) return;
    idx = ((idx % slides.length) + slides.length) % slides.length;
    currentSlide = idx;
    const { verse, hadith } = slides[idx];

    // Show content, hide skeleton
    document.getElementById('nametsQsSkeleton').style.display  = 'none';
    document.getElementById('nametsQsContent').style.display   = 'flex';

    document.getElementById('nametsQsArabic').textContent      = verse.arabic;
    document.getElementById('nametsQsTranslation').textContent = verse.translation;
    document.getElementById('nametsQsReference').textContent   = verse.reference;

    // Hadith
    const hadithBlock = document.getElementById('nametsQsHadith');
    const divider     = document.getElementById('nametsQsDivider');

    if (hadith) {
      document.getElementById('nametsQsHadithArabic').textContent = hadith.arabic;
      document.getElementById('nametsQsHadithText').textContent   = hadith.text;
      document.getElementById('nametsQsHadithSource').textContent = hadith.source;
      hadithBlock.style.display = 'flex';
      divider.style.display     = 'block';
    } else {
      hadithBlock.style.display = 'none';
      divider.style.display     = 'none';
    }

    // Dots
    document.querySelectorAll('.namets-qs-dot').forEach((d, i) => {
      d.classList.toggle('namets-dot-on', i === idx);
    });
  }

  function buildDots() {
    const container = document.getElementById('nametsQsDots');
    if (!container) return;
    container.innerHTML = '';
    slides.forEach((_, i) => {
      const btn = document.createElement('button');
      btn.className = 'namets-qs-dot' + (i === 0 ? ' namets-dot-on' : '');
      btn.setAttribute('aria-label', `Verse ${i + 1}`);
      btn.addEventListener('click', () => renderSlide(i));
      container.appendChild(btn);
    });
  }

  // Auto-rotate verses every 12 seconds
  function startVerseRotation() {
    setInterval(() => {
      if (slides.length > 1) renderSlide(currentSlide + 1);
    }, 12000);
  }

  /* ── Prayer Logic ─────────────────────────────────────────────────────── */

  const PRAYER_META = [
    { key: 'Fajr',    label: 'Fajr',    arabic: 'الفجر',  icon: '🌙' },
    { key: 'Dhuhr',   label: 'Dhuhr',   arabic: 'الظهر',  icon: '☀️' },
    { key: 'Asr',     label: 'Asr',     arabic: 'العصر',  icon: '🌤️' },
    { key: 'Maghrib', label: 'Maghrib', arabic: 'المغرب', icon: '🌅' },
    { key: 'Isha',    label: 'Isha',    arabic: 'العشاء', icon: '🌑' },
  ];

  function getNextPrayer(times) {
    const now = new Date();
    for (const meta of PRAYER_META) {
      const t = times[meta.key];
      if (t > now) return meta;
    }
    // All prayers passed — next is tomorrow's Fajr
    return PRAYER_META[0];
  }

  function isInProgress(times) {
    const now   = new Date();
    const limit = CONFIG.inProgressMinutes * 60 * 1000;
    for (const meta of PRAYER_META) {
      const t = times[meta.key];
      if (now >= t && (now - t) <= limit) return meta;
    }
    return null;
  }

  function renderPrayerTiles(times) {
    const container = document.getElementById('namesPbPrayers');
    if (!container) return;
    const now         = new Date();
    const inProg      = isInProgress(times);
    const next        = getNextPrayer(times);

    container.innerHTML = PRAYER_META.map(meta => {
      const t       = times[meta.key];
      const passed  = t < now && !inProg?.key.startsWith(meta.key);
      const isNext  = meta.key === next.key && !inProg;
      const isIP    = inProg && meta.key === inProg.key;

      let cls = 'namets-pb-tile';
      if (isIP)   cls += ' namets-pb-tile--inprogress';
      else if (isNext) cls += ' namets-pb-tile--next';
      else if (passed) cls += ' namets-pb-tile--passed';

      const badge = isIP ? '<div class="namets-pb-tile-badge"></div>' : '';

      return `
        <div class="${cls}" title="${meta.label} — ${formatTime12(t)}">
          ${badge}
          <span class="namets-pb-tile-icon">${meta.icon}</span>
          <span class="namets-pb-tile-name">${meta.label}</span>
          <span class="namets-pb-tile-arabic">${meta.arabic}</span>
          <span class="namets-pb-tile-time">${formatTime12(t)}</span>
        </div>`;
    }).join('');
  }

  function updateCountdown(times) {
    const cdEl   = document.getElementById('namesPbCountdown');
    const ipEl   = document.getElementById('namesPbInProgress');
    const lblEl  = document.getElementById('namesPbNextLabel');
    if (!cdEl || !ipEl) return;

    const inProg = isInProgress(times);

    if (inProg) {
      cdEl.style.display  = 'none';
      ipEl.style.display  = 'flex';
      lblEl.textContent   = inProg.label + ' Prayer';
    } else {
      ipEl.style.display  = 'none';
      cdEl.style.display  = 'block';

      const next  = getNextPrayer(times);
      const now   = new Date();
      let target  = times[next.key];

      // If all done today, add 24h to Fajr
      if (target <= now) {
        target = new Date(times['Fajr'].getTime() + 86400000);
      }

      const diff  = target - now;
      const h     = Math.floor(diff / 3600000);
      const m     = Math.floor((diff % 3600000) / 60000);
      const s     = Math.floor((diff % 60000) / 1000);

      cdEl.textContent  = `${pad(h)}:${pad(m)}:${pad(s)}`;
      lblEl.textContent = `${next.label} in`;
    }

    // Re-render tiles every minute (state may have changed)
    renderPrayerTiles(times);
  }

  /* ── Hijri Date Display ──────────────────────────────────────────────── */

  function renderDates(hijri) {
    const hijriEl = document.getElementById('namesPbHijri');
    const gregEl  = document.getElementById('namesPbGreg');

    if (hijriEl && hijri) {
      hijriEl.innerHTML =
        `${hijri.day} ${hijri.monthName} ${hijri.year} AH`;
    }

    if (gregEl) {
      gregEl.textContent = new Date().toLocaleDateString('en-GB', {
        weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
      });
    }
  }

  /* ── AlAdhan API Fetch ───────────────────────────────────────────────── */

  async function fetchPrayerData() {
    const today   = new Date();
    const dd      = pad(today.getDate());
    const mm      = pad(today.getMonth() + 1);
    const yyyy    = today.getFullYear();
    const url     = `https://api.aladhan.com/v1/timings/${dd}-${mm}-${yyyy}?latitude=${CONFIG.lat}&longitude=${CONFIG.lng}&method=${CONFIG.method}`;

    try {
      const res  = await fetch(url);
      const json = await res.json();

      if (json.code !== 200) throw new Error('API error');

      const t = json.data.timings;
      const h = json.data.date.hijri;

      // Convert prayer time strings to today's Date objects
      const times = {};
      ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha'].forEach(k => {
        times[k] = timeToDate(t[k]);
      });

      const hijri = {
        day:       parseInt(h.day),
        month:     parseInt(h.month.number),
        monthName: h.month.en,
        year:      parseInt(h.year),
      };

      return { times, hijri };
    } catch (e) {
      console.warn('[NAMETS] Prayer API failed, using fallback times.', e);
      // Sensible fallback for ABU Zaria
      return {
        times: {
          Fajr:    timeToDate('05:15'),
          Dhuhr:   timeToDate('12:30'),
          Asr:     timeToDate('15:45'),
          Maghrib: timeToDate('18:20'),
          Isha:    timeToDate('19:45'),
        },
        hijri: null,
      };
    }
  }

  /* ── Al-Quran.cloud API Fetch (for richer Arabic) ───────────────────── */
  // We keep curated Arabic in the library but this can enrich it from API.
  // Called optionally — if it fails, curated content shows fine.

  async function fetchVerseFromAPI(surah, ayah) {
    try {
      const url = `https://api.alquran.cloud/v1/ayah/${surah}:${ayah}/editions/quran-uthmani,en.asad`;
      const res = await fetch(url);
      const json = await res.json();
      if (json.code !== 200) return null;
      return {
        arabic:      json.data[0]?.text,
        translation: `"${json.data[1]?.text}"`,
      };
    } catch {
      return null;
    }
  }

  /* ── Initialise ──────────────────────────────────────────────────────── */

  async function init() {
    // 1. Set Gregorian date immediately (no API needed)
    const gregEl = document.getElementById('namesPbGreg');
    if (gregEl) {
      gregEl.textContent = new Date().toLocaleDateString('en-GB', {
        weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
      });
    }

    // 2. Fetch prayer times + Hijri date from AlAdhan
    const { times, hijri } = await fetchPrayerData();
    prayerTimes = times;
    hijriData   = hijri;

    // 3. Render prayer bar
    renderDates(hijri);
    renderPrayerTiles(times);
    updateCountdown(times);

    // 4. Live countdown — tick every second
    if (countdownTimer) clearInterval(countdownTimer);
    countdownTimer = setInterval(() => updateCountdown(prayerTimes), 1000);

    // 5. Detect context (Ramadan / Friday / Eid / Default)
    const context = getContext(hijri);

    // 6. Build slide deck, render context banner
    slides = buildSlides(context);
    buildDots();
    renderContextBanner(context);
    renderSlide(0);
    startVerseRotation();

    // 7. (Optional) Enrich first verse from API
    if (slides[0]?.verse?.surah) {
      const rich = await fetchVerseFromAPI(slides[0].verse.surah, slides[0].verse.ayah);
      if (rich && rich.arabic) {
        // Update the stored verse silently, re-render if still on slide 0
        slides[0].verse.arabic      = rich.arabic;
        slides[0].verse.translation = rich.translation;
        if (currentSlide === 0) renderSlide(0);
      }
    }

    // 8. Refresh prayer times at midnight
    scheduleNextDayRefresh();
  }

  function scheduleNextDayRefresh() {
    const now         = new Date();
    const midnight    = new Date(now);
    midnight.setHours(24, 0, 30, 0); // 00:00:30 next day
    const msToMidnight = midnight - now;
    setTimeout(() => { init(); }, msToMidnight);
  }

  /* ── Boot ────────────────────────────────────────────────────────────── */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
