const state = { plans: [], selected: null };
const projects = document.getElementById('projects');
const main = document.getElementById('main');
const refresh = document.getElementById('refresh');

function el(tag, options = {}) {
  const node = document.createElement(tag);
  if (options.id) node.id = options.id;
  if (options.className) node.className = options.className;
  if (options.text !== undefined) node.textContent = options.text;
  if (options.type) node.type = options.type;
  return node;
}

function selectedPlan() {
  return state.plans.find((plan) => plan.id === state.selected) || state.plans[0] || null;
}

function renderProjects() {
  projects.replaceChildren();
  for (const plan of state.plans) {
    const button = el('button', { className: plan.id === state.selected ? 'project active' : 'project', type: 'button' });
    button.append(el('strong', { text: plan.title }));
    const status = plan.briefing?.state ? plan.briefing.state.replaceAll('_', ' ') : 'needs a brief';
    button.append(el('span', { text: status }));
    button.addEventListener('click', () => {
      state.selected = plan.id;
      render();
      main.focus();
    });
    projects.append(button);
  }
}

function row(label, value) {
  const wrapper = el('div', { className: 'brief-row' });
  wrapper.append(el('dt', { text: label }), el('dd', { text: value || 'Not available yet' }));
  return wrapper;
}

async function choose(plan, option) {
  const status = document.getElementById('choice-status');
  status.textContent = 'Saving your choice locally…';
  const response = await fetch('/api/decision', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan: plan.path, option_id: option.id, revision: plan.outcome.revision }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Choice could not be saved.');
  status.textContent = 'Choice received locally. Your coding host still needs to apply it.';
  document.querySelectorAll('.choice').forEach((button) => { button.disabled = true; });
}

function renderPlan(plan) {
  main.replaceChildren();
  if (!plan) {
    const card = el('section', { className: 'card empty' });
    card.append(el('p', { className: 'eyebrow', text: 'Get started' }));
    card.append(el('h2', { text: 'Add your first project' }));
    card.append(el('p', { text: 'Run pilot-puppy init --here in a Git project, then refresh.' }));
    main.append(card);
    return;
  }
  if (!plan.outcome) {
    const card = el('section', { className: 'card empty' });
    card.append(el('p', { className: 'eyebrow', text: plan.title }));
    card.append(el('h2', { text: 'This plan needs an Operator Brief' }));
    card.append(el('p', { text: plan.contract_error || 'Add the typed Outcome fields to PLAN.md.' }));
    main.append(card);
    return;
  }
  const outcome = plan.outcome.outcome;
  const briefing = plan.briefing;
  const card = el('article', { className: `card state-${briefing.state}` });
  const head = el('div', { className: 'card-head' });
  head.append(el('span', { className: 'status', text: briefing.state.replaceAll('_', ' ') }));
  head.append(el('span', { className: 'project-name', text: plan.title }));
  card.append(head);
  card.append(el('p', { className: 'eyebrow', text: 'Outcome' }));
  card.append(el('h2', { text: outcome.summary }));
  card.append(el('p', { className: 'current', text: outcome.current_move }));

  const roleGuide = el('section', { className: 'role-guide' });
  roleGuide.append(el('p', { className: 'eyebrow', text: 'Choose the work shape' }));
  const roles = el('dl', { className: 'role-guide-list' });
  [
    ['Ambiguous decision', 'planner'],
    ['Ordinary bounded change', 'dev'],
    ['Reproducible failure', 'debug'],
    ['Difficult, proof-heavy build', 'hard-dev'],
  ].forEach(([work, role]) => {
    const item = el('div', { className: 'role-guide-item' });
    item.append(el('dt', { text: work }), el('dd', { text: role }));
    roles.append(item);
  });
  roleGuide.append(roles);
  roleGuide.append(el('p', {
    className: 'role-guide-note',
    text: 'Run pilot-puppy route explicitly when the task is ready. It launches nothing.',
  }));
  card.append(roleGuide);

  const brief = el('dl', { className: 'brief' });
  brief.append(row('What changed', briefing.changed));
  brief.append(row('Why it matters', briefing.matters));
  brief.append(row('Recommendation', briefing.recommendation));
  card.append(brief);

  if (briefing.choices.length) {
    const choices = el('section', { className: 'choices' });
    choices.append(el('p', { className: 'eyebrow', text: briefing.blocker || 'Choose the next move' }));
    briefing.choices.forEach((option, index) => {
      const button = el('button', { className: 'choice', type: 'button' });
      button.append(el('span', { className: 'choice-letter', text: String.fromCharCode(65 + index) }));
      const copy = el('span', { className: 'choice-copy' });
      copy.append(el('strong', { text: option.label }), el('small', { text: option.consequence }));
      button.append(copy);
      button.addEventListener('click', async () => {
        try { await choose(plan, option); } catch (error) { document.getElementById('choice-status').textContent = error.message; }
      });
      choices.append(button);
    });
    choices.append(el('p', { id: 'choice-status', className: 'choice-status', text: 'Nothing is sent until you choose.' }));
    card.append(choices);
  }

  const proof = el('details', { className: 'proof' });
  proof.append(el('summary', { text: briefing.proof ? 'See proof' : 'No proof yet' }));
  if (briefing.proof) {
    proof.append(el('p', { text: briefing.proof.verification_summary }));
    proof.append(el('code', { text: briefing.proof.locator }));
  } else {
    proof.append(el('p', { text: 'The plan does not name verified proof yet.' }));
  }
  card.append(proof);
  main.append(card);
}

function render() {
  const plan = selectedPlan();
  if (plan && !state.selected) state.selected = plan.id;
  renderProjects();
  renderPlan(plan);
}

async function load() {
  refresh.disabled = true;
  try {
    const response = await fetch('/api/plans');
    if (!response.ok) throw new Error('Pilot Puppy could not read plans.');
    const data = await response.json();
    state.plans = Array.isArray(data.plans) ? data.plans : [];
    if (!state.plans.some((plan) => plan.id === state.selected)) state.selected = state.plans[0]?.id || null;
    render();
  } catch (error) {
    main.replaceChildren(el('p', { className: 'error', text: error.message }));
  } finally {
    refresh.disabled = false;
  }
}

refresh.addEventListener('click', load);
load();
