/* ── Reloading Tracker Webapp – Client JS ── */

// Cached powder data for current setup
let powderData = null;

// ── Accordion ───────────────────────────────────────────────

function toggleStep(step) {
    const accordion = document.querySelector(`[data-step="${step}"]`);
    const header = accordion.querySelector('.accordion-header');
    const body = accordion.querySelector('.accordion-body');
    const isOpen = body.classList.contains('open');

    // Close all
    document.querySelectorAll('.accordion-header').forEach(h => h.classList.remove('active'));
    document.querySelectorAll('.accordion-body').forEach(b => b.classList.remove('open'));

    // Toggle clicked
    if (!isOpen) {
        header.classList.add('active');
        body.classList.add('open');
    }
}

// ── Powder info ─────────────────────────────────────────────

async function loadPowderInfo() {
    const setupId = document.getElementById('setup_id').value;
    const banner = document.getElementById('powder-info');
    if (!setupId) {
        banner.classList.add('hidden');
        powderData = null;
        return;
    }

    try {
        const resp = await fetch(`/api/setup/${setupId}/powder`);
        powderData = await resp.json();

        if (powderData.powder_name) {
            document.getElementById('powder-name').textContent = powderData.powder_name;
            const range = powderData.charge_min_gr && powderData.charge_max_gr
                ? `${powderData.charge_min_gr} – ${powderData.charge_max_gr} gr`
                : '';
            document.getElementById('powder-range').textContent = range;
            banner.classList.remove('hidden');
        } else {
            banner.classList.add('hidden');
        }

        // Re-check charge with new data
        checkCharge();
    } catch (e) {
        powderData = null;
        banner.classList.add('hidden');
    }
}

// ── Charge warning ──────────────────────────────────────────

function checkCharge() {
    const charge = parseFloat(document.getElementById('charge_gr').value);
    const indicator = document.getElementById('charge-warning');
    indicator.className = 'charge-indicator';

    if (!charge || !powderData || !powderData.charge_max_gr) return;

    const max = powderData.charge_max_gr;
    const ratio = charge / max;

    if (ratio > 1.0) {
        indicator.classList.add('charge-danger');
    } else if (ratio > 0.95) {
        indicator.classList.add('charge-caution');
    } else {
        indicator.classList.add('charge-safe');
    }
}

// ── Jump calculation ────────────────────────────────────────

function calcJump() {
    const cbto = parseFloat(document.getElementById('cbto_mm').value);
    const display = document.getElementById('jump-display');

    if (!cbto || !powderData || !powderData.cbto_lands_mm) {
        display.textContent = '—';
        return;
    }

    const jumpMm = powderData.cbto_lands_mm - cbto;
    const jumpThou = (jumpMm / 25.4) * 1000;
    display.textContent = `${jumpMm.toFixed(2)} mm (${jumpThou.toFixed(1)} thou)`;
}

// ── Velocity fields ─────────────────────────────────────────

function updateVelocityFields() {
    const n = parseInt(document.getElementById('nb_coups').value) || 5;
    const container = document.getElementById('velocity-fields');

    // Save existing values
    const existing = [];
    container.querySelectorAll('input').forEach(inp => {
        existing.push(inp.value);
    });

    container.innerHTML = '';
    for (let i = 0; i < n; i++) {
        const input = document.createElement('input');
        input.type = 'number';
        input.inputMode = 'numeric';
        input.placeholder = `V${i + 1}`;
        input.step = '1';
        input.addEventListener('input', calcStats);
        if (existing[i]) input.value = existing[i];
        container.appendChild(input);
    }
}

// ── Stats calculation ───────────────────────────────────────

function calcStats() {
    const inputs = document.querySelectorAll('#velocity-fields input');
    const velocities = [];
    inputs.forEach(inp => {
        const v = parseFloat(inp.value);
        if (!isNaN(v) && v > 0) velocities.push(v);
    });

    const vmoyEl = document.getElementById('stat-vmoy');
    const esEl = document.getElementById('stat-es');
    const sdEl = document.getElementById('stat-sd');

    if (velocities.length === 0) {
        vmoyEl.textContent = '—';
        esEl.textContent = '—';
        esEl.className = 'text-lg font-bold';
        sdEl.textContent = '—';
        return;
    }

    // Mean
    const mean = velocities.reduce((a, b) => a + b, 0) / velocities.length;
    vmoyEl.textContent = Math.round(mean) + ' fps';

    if (velocities.length >= 2) {
        // ES
        const es = Math.max(...velocities) - Math.min(...velocities);
        esEl.textContent = Math.round(es);
        esEl.className = 'text-lg font-bold es-' + esColor(es);

        // SD
        const variance = velocities.reduce((sum, v) => sum + (v - mean) ** 2, 0) / (velocities.length - 1);
        const sd = Math.sqrt(variance);
        sdEl.textContent = sd.toFixed(1);
    } else {
        esEl.textContent = '—';
        esEl.className = 'text-lg font-bold';
        sdEl.textContent = '—';
    }
}

function esColor(es) {
    if (es < 15) return 'green';
    if (es <= 30) return 'orange';
    return 'red';
}

// ── MOA calculation ─────────────────────────────────────────

function calcMoa() {
    const grp = parseFloat(document.getElementById('groupement_mm').value);
    const dist = parseFloat(document.getElementById('distance_m').value) || 100;
    const display = document.getElementById('moa-display');

    if (!grp || grp <= 0) {
        display.textContent = '—';
        return;
    }

    // 1 MOA ≈ 29.089 mm at 100m
    const moa = grp / (29.089 * dist / 100);
    display.textContent = moa.toFixed(2) + ' MOA';
}

// ── Form submission ─────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('session-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const setupId = document.getElementById('setup_id').value;
        if (!setupId) {
            showToast('Sélectionnez un setup', true);
            return;
        }

        const chargeGr = parseFloat(document.getElementById('charge_gr').value);
        if (!chargeGr) {
            showToast('Saisissez la charge', true);
            return;
        }

        // Collect velocities
        const vitesses = [];
        document.querySelectorAll('#velocity-fields input').forEach(inp => {
            const v = parseFloat(inp.value);
            if (!isNaN(v) && v > 0) vitesses.push(v);
        });

        // Collect pressure signs
        const signes = [];
        document.querySelectorAll('input[name="pression"]:checked').forEach(cb => {
            signes.push(cb.value);
        });

        // Collect meteo
        const meteo = {};
        ['temperature', 'vent_force', 'vent_dir', 'hygro', 'altitude', 'pression'].forEach(key => {
            const el = document.getElementById('meteo_' + key);
            if (el && el.value) meteo[key] = el.value;
        });

        // Compute jump
        let jumpMm = null;
        const cbto = parseFloat(document.getElementById('cbto_mm').value);
        if (cbto && powderData && powderData.cbto_lands_mm) {
            jumpMm = powderData.cbto_lands_mm - cbto;
        }

        const data = {
            setup_id: parseInt(setupId),
            date: document.getElementById('date').value,
            lieu: document.getElementById('lieu').value,
            phase: document.getElementById('phase').value,
            meteo: meteo,
            charge_gr: chargeGr,
            oal_mm: parseFloat(document.getElementById('oal_mm').value) || null,
            cbto_mm: cbto || null,
            jump_mm: jumpMm,
            nb_coups: parseInt(document.getElementById('nb_coups').value) || 5,
            distance_m: parseFloat(document.getElementById('distance_m').value) || 100,
            vitesses: vitesses,
            groupement_mm: parseFloat(document.getElementById('groupement_mm').value) || null,
            signes_pression: signes,
            observations: document.getElementById('observations').value,
        };

        const btn = document.getElementById('btn-save');
        btn.disabled = true;
        btn.textContent = 'Enregistrement...';

        try {
            const resp = await fetch('/api/session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            const result = await resp.json();

            if (result.ok) {
                showToast('Session enregistrée !');
                // Reset form after short delay
                setTimeout(() => {
                    // Keep setup & date, reset the rest
                    document.getElementById('charge_gr').value = '';
                    document.getElementById('oal_mm').value = '';
                    document.getElementById('cbto_mm').value = '';
                    document.getElementById('groupement_mm').value = '';
                    document.getElementById('observations').value = '';
                    document.getElementById('jump-display').textContent = '—';
                    document.getElementById('moa-display').textContent = '—';
                    document.getElementById('charge-warning').className = 'charge-indicator';
                    document.querySelectorAll('input[name="pression"]').forEach(cb => cb.checked = false);
                    updateVelocityFields();
                    calcStats();
                    // Go back to step B for next serie
                    toggleStep('B');
                }, 800);
            } else {
                showToast(result.error || 'Erreur', true);
            }
        } catch (err) {
            showToast('Erreur réseau', true);
        } finally {
            btn.disabled = false;
            btn.textContent = 'Enregistrer la session';
        }
    });
});

// ── Toast ────────────────────────────────────────────────────

function showToast(msg, isError = false) {
    const toast = document.getElementById('toast');
    const msgEl = document.getElementById('toast-msg');
    msgEl.textContent = msg;
    toast.className = isError ? 'toast error' : 'toast';
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 2500);
}
