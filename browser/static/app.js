const state = { plans: [], selected: null, drives: {}, view: 'briefs' };
const projects = document.getElementById('projects');
const main = document.getElementById('main');
const refresh = document.getElementById('refresh');
const board = document.getElementById('board');
const shell = document.querySelector('.shell');
const viewBoard = document.getElementById('view-board');
const viewBriefs = document.getElementById('view-briefs');

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
  status.textContent = 'Saving your choice on this computer…';
  const response = await fetch('/api/decision', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan: plan.path, option_id: option.id, revision: plan.outcome.revision }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Choice could not be saved.');
  status.textContent = 'Choice saved. Nothing starts until you ask.';
  document.querySelectorAll('.choice').forEach((button) => { button.disabled = true; });
}

async function drive(plan, action, session) {
  const endpoint = {
    prepare: '/api/drive/prepare',
    launch: '/api/drive/launch',
    accept: '/api/drive/accept',
  }[action];
  const body = action === 'prepare' ? { plan: plan.path } : { plan: plan.path, session };
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok || !data.drive) throw new Error(data.error || 'Shadow could not update this work.');
  return data.drive;
}

function workButton(label, listener) {
  const button = el('button', { className: 'work-button', type: 'button', text: label });
  button.addEventListener('click', listener);
  return button;
}

function renderReadyWork(plan) {
  const details = plan.drive;
  if (!details) return null;
  const work = el('section', { className: 'ready-work' });
  if (details.state === 'needs_attention') {
    work.append(el('p', { className: 'eyebrow', text: 'Ready work' }));
    work.append(el('h3', { text: 'This work list needs a quick tidy-up first.' }));
    work.append(el('p', { text: 'Shadow will not start anything until the plan is clear and safe.' }));
    return work;
  }
  if (details.state === 'nothing_ready') {
    work.append(el('p', { className: 'eyebrow', text: 'Ready work' }));
    work.append(el('h3', { text: 'Nothing is ready to start yet.' }));
    work.append(el('p', { text: 'When a plan has clear, separate pieces of work, they will appear here.' }));
    return work;
  }
  const remembered = state.drives[plan.id];
  if (remembered?.state === 'accepted') {
    work.append(el('p', { className: 'eyebrow', text: 'Work update' }));
    work.append(el('h3', { text: 'The checked work is in this project.' }));
    work.append(el('p', { text: `Finished and checked: ${remembered.finished_count}.` }));
    work.append(el('p', { className: 'work-note', text: 'Shadow checked it again in a separate clean copy, then added it here. Nothing was sent anywhere.' }));
    return work;
  }
  if (remembered?.state === 'finished') {
    work.append(el('p', { className: 'eyebrow', text: 'Work update' }));
    const allFinished = remembered.finished_count === remembered.work_count;
    work.append(el('h3', { text: allFinished ? 'Your checked work is ready.' : 'Some work needs your attention.' }));
    work.append(el('p', { text: `Finished and checked: ${remembered.finished_count}. Needs your attention: ${remembered.needs_attention_count}.` }));
    work.append(el('p', { className: 'work-note', text: allFinished ? 'Nothing has been added to this project yet. Nothing was sent anywhere.' : 'The finished changes are kept safely aside. Nothing was added to this project or sent anywhere.' }));
    if (allFinished) {
      const status = el('p', { className: 'work-status', text: 'Shadow will check this work again before adding it here.' });
      const button = workButton('Bring checked work into this project', async () => {
        button.disabled = true;
        status.textContent = 'Checking the work one more time, then adding it here…';
        try {
          state.drives[plan.id] = await drive(plan, 'accept', remembered.session);
          render();
        } catch (error) {
          status.textContent = error.message;
          button.disabled = false;
        }
      });
      work.append(button, status);
    }
    return work;
  }
  work.append(el('p', { className: 'eyebrow', text: remembered ? 'Ready to start' : 'Ready work' }));
  work.append(el('h3', { text: remembered ? 'These pieces are ready to go.' : 'Here is work Shadow can prepare.' }));
  work.append(el('p', {
    text: remembered
      ? 'Starting is a one-time, foreground action. Shadow uses the coding tools already on this computer.'
      : 'Shadow can set up up to three separate pieces at a time. It will not start a coding tool until you say so.',
  }));
  const list = el('ul', { className: 'ready-list' });
  details.lanes.filter((lane) => lane.state === 'ready').forEach((lane) => list.append(el('li', { text: lane.summary })));
  work.append(list);
  const status = el('p', {
    className: 'work-status',
    text: remembered ? 'Nothing has started until you press Start ready work.' : 'Nothing has started.',
  });
  const action = remembered ? 'launch' : 'prepare';
  const label = remembered ? 'Start ready work' : 'Prepare ready work';
  const button = workButton(label, async () => {
    button.disabled = true;
    status.textContent = action === 'prepare' ? 'Getting this work ready on this computer…' : 'Starting this work now…';
    try {
      state.drives[plan.id] = await drive(plan, action, remembered?.session);
      render();
    } catch (error) {
      status.textContent = error.message;
      button.disabled = false;
    }
  });
  work.append(button, status);
  return work;
}

function renderPlan(plan) {
  main.replaceChildren();
  if (!plan) {
    const card = el('section', { className: 'card empty' });
    card.append(el('p', { className: 'eyebrow', text: 'Get started' }));
    card.append(el('h2', { text: 'Add your first project' }));
    card.append(el('p', { text: 'Run shadow init --here in a Git project, then refresh.' }));
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
  card.append(el('p', { className: 'eyebrow', text: 'Now' }));
  card.append(el('p', { className: 'current', text: outcome.current_move }));

  const roleGuide = el('section', { className: 'role-guide' });
  roleGuide.append(el('p', { className: 'eyebrow', text: 'How Shadow can help' }));
  const roles = el('dl', { className: 'role-guide-list' });
  [
    ['Think it through', 'When the next move is still unclear.'],
    ['Make a small change', 'For one clear improvement.'],
    ['Fix something broken', 'When you can point to what went wrong.'],
    ['Take on a hard build', 'When the work needs extra care and checking.'],
  ].forEach(([work, explanation]) => {
    const item = el('div', { className: 'role-guide-item' });
    item.append(el('dt', { text: work }), el('dd', { text: explanation }));
    roles.append(item);
  });
  roleGuide.append(roles);
  roleGuide.append(el('p', {
    className: 'role-guide-note',
    text: 'Shadow picks from the coding tools already on this computer. It never starts one without your say-so.',
  }));
  card.append(roleGuide);

  const readyWork = renderReadyWork(plan);
  if (readyWork) card.append(readyWork);

  const brief = el('dl', { className: 'brief' });
  brief.append(row('Change', briefing.changed));
  brief.append(row('Why it matters', briefing.matters));
  brief.append(row('Recommendation', briefing.recommendation));
  card.append(brief);

  if (briefing.choices.length) {
    const choices = el('section', { className: 'choices' });
    choices.append(el('p', { className: 'eyebrow', text: 'Choose what happens next' }));
    choices.append(el('p', { className: 'choice-question', text: briefing.blocker || 'Choose the next move' }));
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
    choices.append(el('p', { id: 'choice-status', className: 'choice-status', text: 'Nothing changes until you choose.' }));
    card.append(choices);
  }

  const proof = el('details', { className: 'proof' });
  proof.append(el('summary', { text: briefing.proof ? 'Proof' : 'Proof not available yet' }));
  if (briefing.proof) {
    proof.append(el('p', { text: briefing.proof.verification_summary }));
    proof.append(el('code', { text: briefing.proof.locator }));
  } else {
    proof.append(el('p', { text: 'The plan does not name verified proof yet.' }));
  }
  card.append(proof);
  main.append(card);
}

function laneName(plan) {
  return plan.entity || 'unassigned';
}

function checkpointMeter(counts) {
  const total = counts.pending + counts.in_progress + counts.blocked + counts.completed;
  if (!total) return null;
  const meter = el('p', { className: 'meter' });
  meter.append(el('span', { className: 'meter-count', text: `Checkpoints ${counts.completed}/${total}` }));
  if (counts.blocked) meter.append(el('span', { className: 'meter-blocked', text: `${counts.blocked} blocked` }));
  return meter;
}

// The board is a read-only projection: its only interactive element is
// card-select. Decisions and Drive stay in the per-plan Briefs view.
function renderBoard() {
  board.replaceChildren();
  const lanes = new Map();
  for (const plan of state.plans) {
    const key = laneName(plan);
    if (!lanes.has(key)) lanes.set(key, []);
    lanes.get(key).push(plan);
  }
  if (!lanes.size) {
    board.append(el('p', { className: 'loading', text: 'No plans yet. Run shadow init --here in a Git project, then refresh.' }));
    return;
  }
  for (const [name, plans] of lanes) {
    const lane = el('section', { className: 'lane' });
    const head = el('div', { className: 'lane-head' });
    head.append(el('h2', { className: 'lane-title', text: name }));
    head.append(el('span', { className: 'lane-count', text: `${plans.length} plan${plans.length === 1 ? '' : 's'}` }));
    lane.append(head);
    const rowEl = el('div', { className: 'lane-cards' });
    const ordered = [...plans].sort((a, b) => Number(a.mode === 'defer') - Number(b.mode === 'defer'));
    for (const plan of ordered) {
      const card = el('button', { className: plan.mode === 'defer' ? 'board-card deferred' : 'board-card', type: 'button' });
      const top = el('div', { className: 'board-card-head' });
      top.append(el('strong', { text: plan.title }));
      if (plan.mode) top.append(el('span', { className: `mode-chip mode-${plan.mode}`, text: plan.mode }));
      card.append(top);
      const status = plan.briefing?.state ? plan.briefing.state.replaceAll('_', ' ') : 'needs a brief';
      card.append(el('span', { className: 'board-state', text: status }));
      if (plan.milestone) card.append(el('p', { className: 'board-milestone', text: plan.milestone }));
      if (plan.checkpoints) {
        const meter = checkpointMeter(plan.checkpoints);
        if (meter) card.append(meter);
      }
      if (plan.briefing?.choices?.length) {
        card.append(el('p', { className: 'board-decision', text: 'A decision is waiting for you' }));
      }
      card.addEventListener('click', () => {
        state.selected = plan.id;
        state.view = 'briefs';
        render();
        main.focus();
      });
      rowEl.append(card);
    }
    lane.append(rowEl);
    board.append(lane);
  }
}

function render() {
  const plan = selectedPlan();
  if (plan && !state.selected) state.selected = plan.id;
  const boardActive = state.view === 'board';
  board.hidden = !boardActive;
  shell.hidden = boardActive;
  viewBoard.classList.toggle('active', boardActive);
  viewBriefs.classList.toggle('active', !boardActive);
  if (boardActive) {
    renderBoard();
    return;
  }
  renderProjects();
  renderPlan(plan);
}

viewBoard.addEventListener('click', () => { state.view = 'board'; render(); });
viewBriefs.addEventListener('click', () => { state.view = 'briefs'; render(); });

async function load() {
  refresh.disabled = true;
  try {
    const response = await fetch('/api/plans');
    if (!response.ok) throw new Error('Shadow could not read plans.');
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
