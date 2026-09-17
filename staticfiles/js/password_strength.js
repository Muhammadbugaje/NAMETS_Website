// static/js/password_strength.js

function scorePassword(pw) {
    let score = 0;
    if (pw.length >= 8) score++;
    if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++;
    if (/\d/.test(pw)) score++;
    if (/[^A-Za-z0-9]/.test(pw)) score++;
    return score;
}

const LABELS = ['Weak', 'Weak', 'Fair', 'Good', 'Strong'];
const COLORS = ['#e53e3e', '#e53e3e', '#d69e2e', '#48bb78', '#38a169'];

document.addEventListener('DOMContentLoaded', function() {
    const input = document.getElementById('id_new_password');
    const bar = document.getElementById('strength-bar');
    const label = document.getElementById('strength-label');

    if (!input || !bar || !label) return;

    input.addEventListener('input', function() {
        const score = scorePassword(this.value);
        const pct = (score / 4) * 100;
        bar.style.width = pct + '%';
        bar.style.backgroundColor = COLORS[score];
        label.textContent = this.value ? LABELS[score] : '';
        label.style.color = COLORS[score];
    });
});