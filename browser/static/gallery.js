// The gallery renders every fixture through the PRODUCTION renderers in
// app.js — renderPlan into the stub #main, renderBoard from a one-plan state —
// and then moves the produced nodes into labeled cells. No card markup is
// duplicated here; if the gallery drifts from the board, the board drifted.

async function buildGallery() {
  const grid = document.getElementById('gallery');
  const stubMain = document.getElementById('main');
  const stubBoard = document.getElementById('board');
  let data;
  try {
    const response = await fetch('/api/gallery');
    if (!response.ok) throw new Error('gallery fixtures unavailable');
    data = await response.json();
  } catch (error) {
    grid.append(Object.assign(document.createElement('p'), { textContent: error.message }));
    return;
  }
  for (const plan of data.plans) {
    const cell = document.createElement('section');
    cell.className = 'gallery-cell';
    const heading = document.createElement('h3');
    heading.textContent = `${plan.gallery_name} — expects "${plan.expected_state}"`;
    cell.append(heading);

    const briefStage = document.createElement('div');
    briefStage.className = 'stage';
    renderPlan(plan);
    while (stubMain.firstChild) briefStage.append(stubMain.firstChild);
    cell.append(briefStage);

    const boardStage = document.createElement('div');
    boardStage.className = 'stage';
    state.plans = [plan];
    renderBoard();
    while (stubBoard.firstChild) boardStage.append(stubBoard.firstChild);
    cell.append(boardStage);

    grid.append(cell);
  }
  state.plans = [];
}

buildGallery();
