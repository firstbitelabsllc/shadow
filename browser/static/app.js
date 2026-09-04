const state = { plans: [], tree: undefined, selected: null, view: 'briefs', boardRevision: null, warning: null };
const projects = document.getElementById('projects');
const main = document.getElementById('main');
const refresh = document.getElementById('refresh');
const board = document.getElementById('board');
const tree = document.getElementById('tree');
const shell = document.querySelector('.shell');
const viewBoard = document.getElementById('view-board');
const viewBriefs = document.getElementById('view-briefs');
const viewTree = document.getElementById('view-tree');
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
    button.append(el('strong', { text: plan.board?.outcome || 'Work' }));
    const status = plan.briefing?.state || plan.board?.state || 'unreadable';
    button.append(stateChip(status));
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

function stateChip(state) {
  const chip = el('span', { className: `status state-chip state-${state}`, text: state.replaceAll('_', ' ') });
  return chip;
}

function renderBoardBriefCard(plan) {
  const brief = plan.board || {};
  const card = el('article', { className: 'card' });
  const fields = el('dl', { className: 'brief' });
  fields.append(row('Outcome', brief.outcome));
  fields.append(row('Now', brief.now));
  fields.append(row('Risk', brief.risk));
  fields.append(row('Decision', brief.decision));
  card.append(fields);
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
      const line = el('p', { className: 'board-now checkpoint' });
      line.append(stateChip(checkpoint.state));
      // availability repeats the state for blocked rows; say it only when
      // it adds something (claimed by whom, or reachable/waiting).
      const extras = [];
      if (checkpoint.availability === 'claimed' && checkpoint.owners?.length) {
        extras.push(`claimed by ${checkpoint.owners.join(', ')}`);
      } else if (!['claimed', checkpoint.state].includes(checkpoint.availability)) {
        extras.push(checkpoint.availability);
      }
      const suffix = extras.length ? ` — ${extras.join(', ')}` : '';
      line.append(el('span', { text: ` ${checkpoint.text}${suffix}` }));
      group.append(line);
    }
  } else {
    const now = milestone.current || milestone.next;
    if (now) group.append(el('p', { className: 'board-now', text: now }));
  }
  if (milestone.dod) {
    const dod = el('dl', { className: 'brief' });
    const wrapper = el('div', { className: 'brief-row' });
    wrapper.append(el('dt', { text: 'Done means' }));
    const dd = el('dd', { className: 'dod' });
    dd.append(el('span', { className: 'dod-text', text: milestone.dod.text }));
    dd.append(stateChip(milestone.dod.state));
    wrapper.append(dd);
    dod.append(wrapper);
    group.append(dod);
  }
  card.append(group);
}

// The board is a read-only projection: its only interactive element is
// card-select.
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
      const status = plan.briefing?.state || plan.board?.state || 'unreadable';
      const card = el('button', { className: `board-card state-${status}`, type: 'button' });
      const top = el('div', { className: 'board-card-head' });
      top.append(el('strong', { text: plan.title }));
      if (plan.mode) top.append(el('span', { className: `mode-chip mode-${plan.mode}`, text: plan.mode }));
      card.append(top);
      card.append(el('span', { className: 'board-state status', text: status.replaceAll('_', ' ') }));
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

function treeText(value, fallback = 'Not available yet') {
  if (value === null || value === undefined || value === '') return fallback;
  if (Array.isArray(value)) return value.length ? value.join(', ') : fallback;
  return String(value);
}

function treeField(label, value, fallback = 'Not available yet') {
  const field = el('div', { className: 'tree-field' });
  field.append(el('dt', { text: label }), el('dd', { text: treeText(value, fallback) }));
  return field;
}

function treeDetails(label, stateValue, content, open = false) {
  const details = el('details', { className: 'tree-node' });
  details.open = open;
  const summary = el('summary', { className: 'tree-summary' });
  summary.append(el('span', { className: 'tree-label', text: label }));
  if (stateValue) summary.append(stateChip(stateValue));
  details.append(summary, content);
  return details;
}

function treeFields(fields) {
  const list = el('dl', { className: 'tree-fields' });
  for (const [label, value, fallback] of fields) list.append(treeField(label, value, fallback));
  return list;
}

function treeCheckpoint(checkpoint) {
  const fields = treeFields([
    ['Ownership', checkpoint.owners?.length ? checkpoint.owners.join(', ') : null],
    ['Proof', checkpoint.proof ? `${treeText(checkpoint.proof.class, 'Proof')} — ${treeText(checkpoint.proof.text)}` : null, 'Proof not available yet'],
    ['Wake', checkpoint.wake, 'No wake recorded'],
  ]);
  const worktrees = el('div', { className: 'tree-worktrees' });
  worktrees.append(el('dt', { text: 'Worktree lifecycle' }));
  const lifecycle = Array.isArray(checkpoint.worktrees) ? checkpoint.worktrees : [];
  if (lifecycle.length) {
    for (const item of lifecycle) {
      worktrees.append(el('dd', { text: `${treeText(item.id, 'Worktree')} — ${treeText(item.state, 'state unavailable')}` }));
    }
  } else {
    worktrees.append(el('dd', { text: 'No associated worktree' }));
  }
  fields.append(worktrees);
  return treeDetails(treeText(checkpoint.id, 'Checkpoint'), checkpoint.state || 'unavailable', fields);
}

function treeMilestone(milestone) {
  const content = el('div', { className: 'tree-children' });
  const counts = milestone.counts || {};
  const total = ['pending', 'in_progress', 'blocked', 'completed']
    .reduce((sum, key) => sum + (Number(counts[key]) || 0), 0);
  content.append(treeFields([
    ['Ownership', milestone.owners?.length ? milestone.owners.join(', ') : null],
    ['Progress', total ? `${Number(counts.completed) || 0}/${total} checkpoints complete` : 'No checkpoints yet'],
  ]));
  const checkpoints = Array.isArray(milestone.checkpoints) ? milestone.checkpoints : [];
  if (checkpoints.length) {
    const group = el('div', { className: 'tree-children' });
    for (const checkpoint of checkpoints) group.append(treeCheckpoint(checkpoint));
    content.append(group);
  } else {
    content.append(el('p', { className: 'tree-empty', text: 'No checkpoints in this milestone yet.' }));
  }
  return treeDetails(treeText(milestone.title, 'Milestone'), milestone.state, content, Boolean(milestone.current));
}

function treeEntity(entity) {
  const content = el('div', { className: 'tree-children' });
  content.append(treeFields([
    ['Ownership', entity.resume ? `resume ${entity.resume}` : null],
    ['Source plan', entity.source_plan],
  ]));
  const milestones = Array.isArray(entity.milestones) ? entity.milestones : [];
  if (milestones.length) {
    const group = el('div', { className: 'tree-children' });
    for (const milestone of milestones) group.append(treeMilestone(milestone));
    content.append(group);
  } else {
    content.append(el('p', { className: 'tree-empty', text: entity.integrity === 'ok' ? 'No milestones in this entity yet.' : 'Plan details are unavailable.' }));
  }
  return treeDetails(treeText(entity.id, 'Entity'), entity.integrity || 'unavailable', content);
}

function treeProject(project) {
  const content = el('div', { className: 'tree-children' });
  content.append(treeFields([['Priority', project.priority]]));
  const entities = Array.isArray(project.entities) ? project.entities : [];
  if (entities.length) {
    for (const entity of entities) content.append(treeEntity(entity));
  } else {
    content.append(el('p', { className: 'tree-empty', text: 'No entities in this project yet.' }));
  }
  return treeDetails(treeText(project.id, 'Project'), null, content, true);
}

function renderTree() {
  tree.replaceChildren();
  if (state.tree === undefined) {
    tree.append(el('p', { className: 'loading', text: 'Reading the plan tree…' }));
    return;
  }
  if (state.tree === null) {
    const card = el('section', { className: 'tree-card empty' });
    card.append(el('h2', { text: 'Plan tree unavailable' }));
    card.append(el('p', { text: 'Shadow could not read the canonical plan tree. Refresh to try again.' }));
    tree.append(card);
    return;
  }
  const projectsInTree = Array.isArray(state.tree.projects) ? state.tree.projects : [];
  if (!projectsInTree.length) {
    const card = el('section', { className: 'tree-card empty' });
    card.append(el('h2', { text: 'No projects in the plan tree yet' }));
    card.append(el('p', { text: 'Run shadow init --here in a Git project, then refresh.' }));
    card.append(el('p', { className: 'tree-authority', text: 'The Tree is a read-only view. Board and plans remain the authority.' }));
    tree.append(card);
    return;
  }
  const root = el('section', { className: 'tree-card' });
  root.append(el('p', { className: 'tree-authority', text: 'The Tree is a read-only view. Board and plans remain the authority.' }));
  const computer = state.tree.computer || {};
  const computerContent = el('div', { className: 'tree-children' });
  computerContent.append(treeFields([
    ['Computer', computer.id],
    ['Board revision', computer.revision],
  ]));
  for (const project of projectsInTree) computerContent.append(treeProject(project));
  root.append(treeDetails(treeText(computer.id, 'Computer'), null, computerContent, true));
  tree.append(root);
}

function render() {
  const plan = selectedPlan();
  if (plan && !state.selected) state.selected = plan.id;
  const boardActive = state.view === 'board';
  const treeActive = state.view === 'tree';
  board.hidden = !boardActive;
  tree.hidden = !treeActive;
  shell.hidden = boardActive || treeActive;
  viewBoard.classList.toggle('active', boardActive);
  viewBriefs.classList.toggle('active', !boardActive && !treeActive);
  viewTree.classList.toggle('active', treeActive);
  if (boardActive) {
    renderBoard();
    return;
  }
  if (treeActive) {
    renderTree();
    return;
  }
  renderProjects();
  renderPlan(plan);
}

viewBoard.addEventListener('click', () => { state.view = 'board'; render(); });
viewBriefs.addEventListener('click', () => { state.view = 'briefs'; render(); });
viewTree.addEventListener('click', () => { state.view = 'tree'; render(); });

async function load() {
  refresh.disabled = true;
  try {
    const response = await fetch('/api/plans');
    if (!response.ok) throw new Error('Shadow could not read plans.');
    const data = await response.json();
    state.plans = Array.isArray(data.plans) ? data.plans : [];
    state.tree = data.tree && typeof data.tree === 'object' ? data.tree : null;
    state.boardRevision = data.root_board_revision;
    state.warning = data.warning || null;
    boardWarning.textContent = state.warning ? `Computer board needs attention: ${state.warning}` : '';
    boardWarning.hidden = !state.warning;
    if (!state.plans.some((plan) => plan.id === state.selected)) state.selected = state.plans[0]?.id || null;
    render();
  } catch (error) {
    boardWarning.hidden = true;
    state.tree = null;
    if (state.view === 'tree') {
      renderTree();
    } else {
      main.replaceChildren(el('p', { className: 'error', text: error.message }));
    }
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
