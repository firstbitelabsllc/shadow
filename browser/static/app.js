const state = { plans: [], selected: null, view: 'briefs', boardRevision: null, warning: null };
const projects = document.getElementById('projects');
const main = document.getElementById('main');
const refresh = document.getElementById('refresh');
const board = document.getElementById('board');
const shell = document.querySelector('.shell');
const viewBoard = document.getElementById('view-board');
const viewBriefs = document.getElementById('view-briefs');
const boardWarning = document.getElementById('board-warning');

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
    const status = plan.board?.state || 'unreadable';
    button.append(el('span', { text: status.replaceAll('_', ' ') }));
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

function renderBoardBriefCard(plan) {
  const brief = plan.board;
  if (!brief || brief.state === 'empty' || brief.state === 'unmigrated') {
    const card = el('section', { className: 'card empty' });
    card.append(el('p', { className: 'eyebrow', text: plan.title }));
    if (brief?.state === 'unmigrated') {
      card.append(el('h2', { text: 'Written before the current plan grammar' }));
      card.append(el('p', { text: 'This plan has content but no task rows Shadow can read. Migrate it with shadow init --here, or leave it as history.' }));
    } else {
      card.append(el('h2', { text: 'This plan has no readable tasks yet' }));
      card.append(el('p', { text: 'Add a ## Tasks section with milestone rows, then refresh.' }));
    }
    main.append(card);
    return;
  }
  const card = el('article', { className: `card state-${brief.state}` });
  const head = el('div', { className: 'card-head' });
  head.append(el('span', { className: 'status', text: brief.state.replaceAll('_', ' ') }));
  head.append(el('span', { className: 'project-name', text: plan.title }));
  card.append(head);
  if (brief.priority) {
    card.append(el('p', { className: 'eyebrow', text: 'Priority' }));
    card.append(el('h2', { text: brief.priority }));
  }
  for (const milestone of rotationOf(plan)) appendMilestone(card, milestone);
  if (brief.contradictions_open) {
    card.append(el('p', {
      className: 'board-contradiction',
      text: `${brief.contradictions_open} open contradiction${brief.contradictions_open === 1 ? '' : 's'} — read before landing work`,
    }));
  }
  if (brief.latest_change) {
    const change = el('dl', { className: 'brief' });
    change.append(row('Latest change', brief.latest_change));
    card.append(change);
  }
  main.append(card);
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
  renderBoardBriefCard(plan);
}

function laneName(plan) {
  return plan.project || 'unassigned';
}

function humanName(value) {
  return value.replaceAll('-', ' ');
}

function checkpointMeter(counts) {
  const total = counts.pending + counts.in_progress + counts.blocked + counts.completed;
  if (!total) return null;
  const meter = el('p', { className: 'meter' });
  meter.append(el('span', { className: 'meter-count', text: `Tasks ${counts.completed}/${total}` }));
  if (counts.blocked) meter.append(el('span', { className: 'meter-blocked', text: `${counts.blocked} blocked` }));
  return meter;
}

function rotationOf(plan) {
  if (Array.isArray(plan.milestones) && plan.milestones.length) return plan.milestones;
  return plan.board?.milestone ? [plan.board.milestone] : [];
}

function appendMilestone(card, milestone) {
  const group = el('section', { className: 'milestone-rotation' });
  group.append(el('p', {
    className: 'eyebrow',
    text: milestone.current === true ? 'Current milestone' : 'Milestone in rotation',
  }));
  group.append(el('p', { className: 'board-milestone', text: milestone.title }));
  const meter = checkpointMeter(milestone.counts);
  if (meter) group.append(meter);
  const checkpoints = Array.isArray(milestone.checkpoints) ? milestone.checkpoints : [];
  if (checkpoints.length) {
    for (const checkpoint of checkpoints) {
      const owner = checkpoint.owners?.length ? ` · ${checkpoint.owners.join(', ')}` : '';
      group.append(el('p', {
        className: 'board-now',
        text: `${checkpoint.state.replaceAll('_', ' ')} · ${checkpoint.availability}: ${checkpoint.text}${owner}`,
      }));
    }
  } else {
    const now = milestone.current || milestone.next;
    if (now) group.append(el('p', { className: 'board-now', text: now }));
  }
  if (milestone.dod) {
    const dod = el('dl', { className: 'brief' });
    dod.append(row('Done means', `${milestone.dod.text} (${milestone.dod.state.replaceAll('_', ' ')})`));
    group.append(dod);
  }
  card.append(group);
}

// The browser is a read-only projection. Cards only select which committed
// plan view to inspect; plan and board writes stay in Shadow's CLI verbs.
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
    head.append(el('h2', { className: 'lane-title', text: humanName(name) }));
    head.append(el('span', { className: 'lane-count', text: `${plans.length} entit${plans.length === 1 ? 'y' : 'ies'}` }));
    lane.append(head);
    const rowEl = el('div', { className: 'lane-cards' });
    for (const plan of plans) {
      const card = el('button', { className: 'board-card', type: 'button' });
      const top = el('div', { className: 'board-card-head' });
      top.append(el('strong', { text: plan.title }));
      if (plan.mode) top.append(el('span', { className: `mode-chip mode-${plan.mode}`, text: plan.mode }));
      card.append(top);
      const status = plan.board?.state || 'unreadable';
      card.append(el('span', { className: 'board-state', text: status.replaceAll('_', ' ') }));
      for (const milestone of rotationOf(plan)) appendMilestone(card, milestone);
      if (plan.lint) {
        if (!plan.lint.parse_ok || plan.lint.blocking) card.classList.add('red');
        const verdict = !plan.lint.parse_ok
          ? 'unreadable'
          : plan.lint.blocking
            ? `lint ${plan.lint.blocking}!`
            : 'lint ✓';
        card.append(el('span', { className: plan.lint.blocking || !plan.lint.parse_ok ? 'lint-chip bad' : 'lint-chip', text: verdict }));
      }

      const counts = rotationOf(plan).length ? null : plan.tasks;
      if (counts) {
        const meter = checkpointMeter(counts);
        if (meter) card.append(meter);
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
    state.boardRevision = data.root_board_revision;
    state.warning = data.warning || null;
    boardWarning.textContent = state.warning ? `Computer board needs attention: ${state.warning}` : '';
    boardWarning.hidden = !state.warning;
    if (!state.plans.some((plan) => plan.id === state.selected)) state.selected = state.plans[0]?.id || null;
    render();
  } catch (error) {
    boardWarning.hidden = true;
    main.replaceChildren(el('p', { className: 'error', text: error.message }));
  } finally {
    refresh.disabled = false;
  }
}

refresh.addEventListener('click', load);
// The gallery page reuses these renderers against fixture data; it must not
// also fetch and render the machine's real plans into its stub surface.
// Bare `data-gallery` reads back as the empty string, so test for the
// attribute's presence rather than its (falsy) value.
if (!('gallery' in document.body.dataset)) load();
