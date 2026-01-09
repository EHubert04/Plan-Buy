let currentProjectId = null;
let allProjects = [];

async function loadData() {
    const res = await fetch('/api/projects');
    allProjects = await res.json();
    renderUI();
}

function renderUI() {
    const nav = document.getElementById('side-nav');
    const grid = document.getElementById('project-grid');
    
    nav.innerHTML = '';
    grid.innerHTML = '';

    allProjects.forEach(p => {
        nav.innerHTML += `<li onclick="openProject(${p.id})">${p.name}</li>`;
        grid.innerHTML += `
            <div class="card" onclick="openProject(${p.id})">
                <h3>${p.name}</h3>
                <p>${p.todos.length} Aufgaben</p>
            </div>`;
    });
}

async function addProject() {
    const name = prompt("Projektname:");
    if (!name) return;
    await fetch('/api/projects', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name})
    });
    loadData();
}

function openProject(id) {
  const project = allProjects.find(p => String(p.id) === String(id));
  if (!project) {
    alert("Projekt nicht gefunden.");
    return;
  }

  currentProjectId = project.id;

  document.getElementById('dashboard').style.display = 'none';
  document.getElementById('project-detail').style.display = 'block';
  document.getElementById('detail-title').innerText = project.name;

  document.getElementById('todo-list').innerHTML =
    project.todos.map((todo) => `
      <li class="${todo.done ? 'completed' : ''}">
        <label>
          <input type="checkbox"
                 class="todo-checkbox"
                 data-id="${todo.id}"
                 ${todo.done ? 'checked' : ''}>
          <span class="todo-text">${todo.content}</span>
        </label>
      </li>
    `).join('');

  document.getElementById('res-list').innerHTML =
    project.resources.map((res) => `
      <li class="${res.purchased ? 'completed' : ''}">
        <span class="res-text">${res.name}</span>
        <input type="number"
               class="res-quantity"
               value="${res.quantity ?? 1}"
               min="1"
               data-id="${res.id}">
        <input type="checkbox"
               class="res-checkbox"
               data-id="${res.id}"
               ${res.purchased ? 'checked' : ''}>
      </li>
    `).join('');

  // Todo Toggle -> DB speichern
  document.querySelectorAll('.todo-checkbox').forEach(cb => {
    cb.addEventListener('change', async (e) => {
      const todoId = e.target.dataset.id;
      const done = e.target.checked;

      const li = e.target.closest('li');
      li.classList.toggle('completed', done);

      const resp = await fetch(`/api/projects/${currentProjectId}/todos/${todoId}`, {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ done })
      });

      if (!resp.ok) {
        li.classList.toggle('completed', !done);
        e.target.checked = !done;
        alert("Fehler beim Speichern (Todo).");
        return;
      }

      const t = project.todos.find(x => String(x.id) === String(todoId));
      if (t) t.done = done;
    });
  });

  // Resource purchased Toggle -> DB speichern
  document.querySelectorAll('.res-checkbox').forEach(cb => {
    cb.addEventListener('change', async (e) => {
      const resId = e.target.dataset.id;
      const purchased = e.target.checked;

      const li = e.target.closest('li');
      li.classList.toggle('completed', purchased);

      const resp = await fetch(`/api/projects/${currentProjectId}/resources/${resId}`, {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ purchased })
      });

      if (!resp.ok) {
        li.classList.toggle('completed', !purchased);
        e.target.checked = !purchased;
        alert("Fehler beim Speichern (Ressource).");
        return;
      }

      const r = project.resources.find(x => String(x.id) === String(resId));
      if (r) r.purchased = purchased;
    });
  });

  // Quantity Änderung -> DB speichern
  document.querySelectorAll('.res-quantity').forEach(inp => {
    inp.addEventListener('change', async (e) => {
      const resId = e.target.dataset.id;
      let quantity = parseInt(e.target.value, 10);
      if (!Number.isFinite(quantity) || quantity < 1) quantity = 1;
      e.target.value = quantity;

      const resp = await fetch(`/api/projects/${currentProjectId}/resources/${resId}`, {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ quantity })
      });

      if (!resp.ok) {
        alert("Fehler beim Speichern (Menge).");
        return;
      }

      const r = project.resources.find(x => String(x.id) === String(resId));
      if (r) r.quantity = quantity;
    });
  });
}

async function saveItem(type) {
    const input = document.getElementById(type === 'todo' ? 'todo-input' : 'res-input');
    const content = input.value;
    if (!content) return;

    await fetch(`/api/projects/${currentProjectId}/items`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({type, content})
    });

    input.value = '';
    loadData().then(() => openProject(currentProjectId));
}

function showDashboard() {
    document.getElementById('dashboard').style.display = 'block';
    document.getElementById('project-detail').style.display = 'none';
}

// --- Drag & Drop für Listen ---
function initSortableList(listElement) {
    if (!listElement) return;

    let draggedItem = null;

    // Setze alle Listeneinträge auf draggable
    listElement.querySelectorAll("li").forEach(li => {
        li.draggable = true;

        li.addEventListener("dragstart", () => {
            draggedItem = li;
            li.classList.add("dragging");
        });

        li.addEventListener("dragend", () => {
            li.classList.remove("dragging");
            draggedItem = null;
        });
    });

    // Dragover Event für Drop
    listElement.addEventListener("dragover", (e) => {
        e.preventDefault();
        const afterElement = getDragAfterElement(listElement, e.clientY);
        if (!draggedItem) return;

        if (afterElement == null) {
            listElement.appendChild(draggedItem);
        } else {
            listElement.insertBefore(draggedItem, afterElement);
        }
    });
}

function getDragAfterElement(container, y) {
    const elements = [...container.querySelectorAll("li:not(.dragging)")];
    let closest = null;
    let closestOffset = Number.NEGATIVE_INFINITY;

    elements.forEach(child => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closestOffset) {
            closestOffset = offset;
            closest = child;
        }
    });

    return closest;
}



loadData();