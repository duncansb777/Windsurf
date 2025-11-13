async function postJSON(url) {
  const resp = await fetch(url, { method: 'POST' });
  if (!resp.ok) throw new Error('Request failed');
  return await resp.json();
}

function setStatus(text) {
  document.getElementById('status').textContent = text;
}

function showTrace(trace) {
  const ol = document.getElementById('trace');
  ol.innerHTML = '';
  trace.forEach(step => {
    const li = document.createElement('li');
    li.textContent = `${step.agent} — ${step.action} [${step.status}]`;
    ol.appendChild(li);
  });
}

function renderFlowMap(trace) {
  const container = document.getElementById('flowmap');
  if (!container) return;
  container.innerHTML = '';
  // Basic styles
  container.style.display = 'flex';
  container.style.flexWrap = 'wrap';
  container.style.alignItems = 'center';
  container.style.gap = '8px';

  // Build a linear flow from the trace
  const steps = Array.isArray(trace) ? trace : [];
  steps.forEach((step, idx) => {
    const box = document.createElement('div');
    box.className = 'agent-box';
    box.style.display = 'inline-flex';
    box.style.alignItems = 'center';
    box.style.gap = '6px';
    box.style.padding = '6px 10px';
    box.style.border = '1px solid #d6bcfa'; // light purple border
    box.style.borderRadius = '8px';
    box.style.background = '#ffffff'; // white box for readability
    box.title = `${step.agent} — ${step.action} [${step.status}]`;

    const robot = document.createElement('span');
    // Icons by agent type: MCP = satellite, LLM = brain, others = robot
    const agentName = (step.agent || '').toLowerCase();
    const isMcp = agentName.includes('mcp');
    const isLlm = agentName.includes('llm') || agentName.includes('agentis');
    robot.textContent = isMcp ? '🛰️' : (isLlm ? '🧠' : '🤖');
    robot.style.color = '#7e22ce';
    const label = document.createElement('span');
    label.textContent = step.agent;
    label.style.color = '#7e22ce'; // purple text
    label.style.fontWeight = '600';

    box.appendChild(robot);
    box.appendChild(label);
    container.appendChild(box);

    if (idx < steps.length - 1) {
      const arrow = document.createElement('span');
      arrow.textContent = '➜';
      arrow.style.opacity = '0.7';
      container.appendChild(arrow);
    }
  });
}

function showPanel(id) {
  const panes = ['pane-discharge','pane-audit','pane-referral','pane-agentis','pane-consent','pane-agentis-referral'];
  panes.forEach(pid => {
    const el = document.getElementById(pid);
    if (!el) return;
    if (pid === id) el.classList.remove('hidden'); else el.classList.add('hidden');
  });
}

function setPre(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}

async function runFlow(path, body) {
  setStatus('Running...');
  try {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {})
    });
    const data = await res.json();
    showTrace(data.trace || []);
    renderFlowMap(data.trace || []);
    // Route rendering by path
    // IMPORTANT: check 'agentis-referral' BEFORE generic 'referral'
    if (path === '/api/agentis-referral') {
      showPanel('pane-agentis-referral');
      // Populate panels (handover, gp-message, share)
      try {
        const result = data.result || {};
        const p = result.prompt || {};
        setPre('referral-llm-system', p.system || '');
        setPre('referral-llm-user', p.user || '');
        setPre('referral-llm-output', result.llm_output || {});
        const ex = result.executed || {};
        setPre('referral-exec-tasks', ex.tasks || []);
        setPre('referral-exec-messages', ex.messages || []);
        let ho = result.handover || {};
        // Fallback: try parse handover from prompt.user JSON if not provided
        if ((!ho.note && !ho.risk_summary) && p.user) {
          try {
            const uj = JSON.parse(p.user);
            const hx = (uj && uj.context && uj.context.handover) || (uj && uj.handover) || (uj && uj.facts && uj.facts.handover);
            if (hx) {
              ho = { note: hx.note || '', risk_summary: hx.risk_summary || '' };
            }
          } catch {}
        }
        setPre('referral-handover-note', ho.note || '');
        setPre('referral-handover-risk', ho.risk_summary || '');
        // GP message fallback: from executed messages input
        let gpMsg = result.gp_message || '';
        if (!gpMsg && Array.isArray(ex.messages) && ex.messages.length > 0) {
          const gpFirst = ex.messages.find(m => (m.input && m.input.to_ref === 'Practitioner/prov-001')) || ex.messages[0];
          gpMsg = (gpFirst && gpFirst.input && gpFirst.input.content) || '';
        }
        setPre('referral-gp-message', gpMsg);
        const sr = result.share_result || {};
        setPre('referral-share-allowed', sr.allowed || []);
        setPre('referral-share-denied', sr.denied || []);
      } catch (e) {}

      // Always show Uber prompt for transport booking
      const promptEl = document.getElementById('uber-prompt');
      const resultEl = document.getElementById('uber-result');
      if (promptEl && resultEl) {
        promptEl.style.display = 'flex';
        resultEl.style.display = 'none';
        resultEl.textContent = '';
      }
    }

  else if (path.includes('discharge')) {
    showPanel('pane-discharge');
    const res = data.result || {};
    setPre('result-discharge-event', res.discharge_event || {});
    setPre('result-patient-bundle', res.patient_bundle || {});
    setPre('result-providers', res.providers || {});
    // Cache the latest discharge context for reuse by Agent Referral
    window.__lastDischarge__ = {
      discharge_event: res.discharge_event || {},
      patient_bundle: res.patient_bundle || {},
      providers: res.providers || {}
    };
    // Toggle denial banner
    const banner = document.getElementById('bundle-denied');
    const pb = res.patient_bundle || {};
    if (pb.denied) {
      banner.classList.remove('hidden');
      banner.textContent = `Patient bundle access denied${pb.reason ? `: ${pb.reason}` : ''}${pb.message ? ` — ${pb.message}` : ''}`;
    } else {
      banner.classList.add('hidden');
    }
  } else if (path.includes('audit-check')) {
    showPanel('pane-audit');
    const res = data.result || {};
    setPre('result-writeback', res.write_back_id || '');
    setPre('result-alert', res.alert_id || '');
    setPre('result-audit', res.audit || {});
  } else if (path.includes('referral')) {
    showPanel('pane-referral');
    const res = data.result || {};
    setPre('result-referrals', res.referrals || {});
    setPre('result-created-task', res.created_task || {});
  } else if (path === '/api/uber') {
    // After booking, keep user on Agent Referral panel and show booking result
    showPanel('pane-agentis-referral');
    const r = data.result || {};
    const resultEl = document.getElementById('uber-result');
    const promptEl = document.getElementById('uber-prompt');
    if (promptEl) promptEl.style.display = 'none';
    if (resultEl) {
      resultEl.style.display = 'block';
      resultEl.textContent = JSON.stringify(r, null, 2);
    }
  } else if (path.includes('agentis')) {
    showPanel('pane-agentis');
    const res = data.result || {};
    const prompt = res.prompt || {};
    setPre('result-llm-system', prompt.system || '');
    setPre('result-llm-user', prompt.user || '');
    setPre('result-llm-output', res.llm_output || {});
  } else if (path.includes('consent-check')) {
    showPanel('pane-consent');
    const res = data.result || {};
    const req = {
      patient_ref: res.patient_ref,
      recipient_ref: res.recipient_ref,
      action: res.action,
      purpose_of_use: res.purpose_of_use,
    };
    setPre('consent-request', req);
    setPre('consent-decision', res.decision || {});
  }
  setStatus('Done');
} catch (e) {
  setStatus('Error: ' + e.message);
}
}

window.addEventListener('DOMContentLoaded', () => {
  // Load patients
  fetch('/api/patients').then(r=>r.json()).then(data => {
    const sel = document.getElementById('patient-select');
    (data.patients || []).forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.patient_id;
      opt.textContent = `${p.patient_id} — ${p.name} (${p.mrn || ''})`;
      sel.appendChild(opt);
    });
  });

  document.getElementById('btn-discharge').addEventListener('click', () => {
    const pid = document.getElementById('patient-select').value;
    runFlow('/api/discharge', { patient_id: pid });
  });
  // Removed: audit and referral buttons
  document.getElementById('btn-agentis').addEventListener('click', () => {
    const pid = document.getElementById('patient-select').value;
    runFlow('/api/agentis', { patient_id: pid });
  });
  document.getElementById('btn-agentis-referral').addEventListener('click', () => {
    const pid = document.getElementById('patient-select').value;
    const ctx = window.__lastDischarge__ || {};
    runFlow('/api/agentis-referral', { patient_id: pid, context: ctx });
  });
  // Uber prompt handlers
  const btnUberYes = document.getElementById('btn-uber-yes');
  if (btnUberYes) {
    btnUberYes.addEventListener('click', async () => {
      const pid = document.getElementById('patient-select').value;
      await runFlow('/api/uber', { patient_id: pid, purpose: 'discharge_transport' });
    });
  }
  const btnUberNo = document.getElementById('btn-uber-no');
  if (btnUberNo) {
    btnUberNo.addEventListener('click', () => {
      const promptEl = document.getElementById('uber-prompt');
      const resultEl = document.getElementById('uber-result');
      if (promptEl) promptEl.style.display = 'none';
      if (resultEl) {
        resultEl.style.display = 'none';
        resultEl.textContent = '';
      }
    });
  }
  document.getElementById('btn-consent').addEventListener('click', () => {
    const pid = document.getElementById('patient-select').value;
    // Example: check consent to share summary to GP Practitioner/123 for treatment
    runFlow('/api/consent-check', {
      patient_id: pid,
      recipient_ref: 'Practitioner/123',
      action: 'share_summary',
      purpose_of_use: 'treatment'
    });
  });
});
