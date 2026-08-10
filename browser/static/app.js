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

// "3 hours ago" — a card never prints an ISO stamp at a person.
function relativeTime(iso) {
  if (!iso) return null;
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return null;
  const seconds = Math.round((Date.now() - then) / 1000);
  if (seconds < 60) return 'just now';
  const units = [[31536000, 'year'], [2592000, 'month'], [604800, 'week'], [86400, 'day'], [3600, 'hour'], [60, 'minute']];
  for (const [size, name] of units) {
    if (Math.abs(seconds) >= size) {
      const count = Math.round(seconds / size);
      return `${count} ${name}${count === 1 ? '' : 's'} ago`;
    }
  }
  return 'just now';
}

function stateChip(state) {
  const chip = el('span', { className: `status state-chip state-${state}`, text: state.replaceAll('_', ' ') });
  return chip;
}

function latestChangeRow(change) {
  // Old plans (and old servers) sent a bare string; render it as-is rather
  // than a blank row, but never invent structure for it.
  const wrapper = el('div', { className: 'brief-row' });
  wrapper.append(el('dt', { text: 'Latest change' }));
  const dd = el('dd', { className: 'change' });
  if (typeof change === 'string') {
    dd.append(el('span', { text: change }));
  } else {
    const meta = el('p', { className: 'change-meta' });
    const when = relativeTime(change.when);
    if (when) meta.append(el('span', { className: 'change-when', text: when }));
    if (change.kind) meta.append(el('span', { className: 'change-kind', text: change.kind }));
    if (meta.childElementCount) dd.append(meta);
    if (change.summary) dd.append(el('p', { className: 'change-summary', text: change.summary }));
    if (!dd.childElementCount) dd.append(el('span', { text: 'Not available yet' }));
  }
  wrapper.append(dd);
  return wrapper;
}

async function choose(plan, option) {
  const status = document.getElementById('choice-status');
  status.textContent = 'Saving your choice on this computer…';
  const response = await fetch('/api/decision', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      entity: plan.entity,
      root_board_revision: state.boardRevision,
      option_id: option.id,
      revision: plan.outcome.revision,
    }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Choice could not be saved.');
  if (data.receipt && data.receipt.state && data.receipt.state !== 'received') {
    status.textContent = 'The plan changed since you loaded it — refreshing; choose again.';
    load();
    return;
  }
  status.textContent = 'Choice saved. Nothing starts until you ask.';
  document.querySelectorAll('.choice').forEach((button) => { button.disabled = true; });
}

function renderBoardBriefCard(plan) {
  const brief = plan.board;
  if (!brief || brief.state === 'empty' || brief.state === 'unmigrated') {
    const card = el('section', { className: 'card empty' });
    card.append(el('p', { className: 'eyebrow', text: plan.title }));
    if (brief?.state === 'unmigrated') {
      card.append(el('h2', { text: 'Written before the current plan grammar' }));
      card.append(el('p', { text: 'This plan has content but no task rows Shadow can read. Migrate it with shadow init --here, or leave it as history.' }));
      // A pre-grammar plan can also carry a broken v3 Outcome. Staying silent
      // about that error would send the owner migrating when the real defect
      // is in the Brief they already have.
      if (plan.contract_error) {
        card.append(el('p', { text: `Its Brief also has an Outcome Shadow could not read: ${plan.contract_error}` }));
      }
    } else {
      card.append(el('h2', { text: 'This plan has no readable tasks yet' }));
      card.append(el('p', { text: plan.contract_error || 'Add a ## Tasks section with milestone rows, then refresh.' }));
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
    // A bare number or code is data, not a headline — keep the hero type
    // for priorities that actually say something.
    const spoken = String(brief.priority).trim();
    card.append(el(spoken.length > 8 ? 'h2' : 'p', {
      className: spoken.length > 8 ? '' : 'current',
      text: spoken,
    }));
  }
  for (const milestone of rotationOf(plan)) appendMilestone(card, milestone);
  if (brief.contradictions_open) {
    const notice = el('p', { className: 'notice' });
    notice.append(el('span', {
      className: 'notice-count',
      text: String(brief.contradictions_open),
    }));
    notice.append(el('span', {
      text: `open contradiction${brief.contradictions_open === 1 ? '' : 's'} to read before landing work`,
    }));
    card.append(notice);
  }
  if (brief.latest_change) {
    const change = el('dl', { className: 'brief' });
    change.append(latestChangeRow(brief.latest_change));
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
  if (!plan.outcome || !plan.briefing) {
    renderBoardBriefCard(plan);
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
  for (const milestone of rotationOf(plan)) appendMilestone(card, milestone);

  const roleGuide = el('section', { className: 'role-guide' });
  roleGuide.append(el('p', { className: 'eyebrow', text: 'How Shadow can help' }));
  const roles = el('dl', { className: 'role-guide-list' });
  [
    ['Drive the full outcome', 'Continue through every reachable requirement.'],
    ['Fan out safe work', 'Claim path-disjoint lanes and integrate their proof.'],
    ['Fix every proven defect', 'Keep going until acceptance or an exact hard rail.'],
    ['Raise every surface', 'Apply the required design, reliability, and release gates.'],
  ].forEach(([work, explanation]) => {
    const item = el('div', { className: 'role-guide-item' });
    item.append(el('dt', { text: work }), el('dd', { text: explanation }));
    roles.append(item);
  });
  roleGuide.append(roles);
  roleGuide.append(el('p', {
    className: 'role-guide-note',
    text: 'Shadow uses supported local coding tools autonomously after durable claims; full acceptance stops the outcome, and only exact hard rails pause it earlier.',
  }));
  card.append(roleGuide);

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
      button.disabled = Boolean(state.warning);
      button.append(el('span', { className: 'choice-letter', text: String.fromCharCode(65 + index) }));
      const copy = el('span', { className: 'choice-copy' });
      copy.append(el('strong', { text: option.label }), el('small', { text: option.consequence }));
      button.append(copy);
      button.addEventListener('click', async () => {
        try { await choose(plan, option); } catch (error) { document.getElementById('choice-status').textContent = error.message; }
      });
      choices.append(button);
    });
    choices.append(el('p', {
      id: 'choice-status',
      className: 'choice-status',
      text: state.warning ? 'Refresh the computer board before choosing.' : 'Nothing changes until you choose.',
    }));
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
// card-select. Decisions stay in the per-plan Briefs view.
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
      const status = plan.briefing?.state || plan.board?.state || 'unreadable';
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
