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
    currentProjectId = id;
    const project = allProjects.find(p => p.id === id);
    
    document.getElementById('dashboard').style.display = 'none';
    document.getElementById('project-detail').style.display = 'block';
    document.getElementById('detail-title').innerText = project.name;

   document.getElementById('todo-list').innerHTML =
    project.todos.map((task, index) => `
      <li>
        <label>
          <input type="checkbox" class="todo-checkbox" data-index="${index}">
          <span class="todo-text">${task}</span>
        </label>
      </li>
    `).join('');

    document.getElementById('res-list').innerHTML =
    project.resources.map((res, index) => `
    <li>
      <span class="res-text">${res.name}</span>
      <input type="number" class="res-quantity" style = "width:50px" value="${res.quantity}" min="1" data-index="${index}">
      <input type="checkbox" class="res-checkbox" data-index="${index}">
    </li>
  `).join('');

    document.querySelectorAll('.todo-checkbox').forEach(checkbox => {
    checkbox.addEventListener('change', (e) => {
        const li = e.target.closest('li');
        if (e.target.checked) {
            li.classList.add('completed'); // durchgestrichen
        } else {
            li.classList.remove('completed');
        }
    });
});


    document.querySelectorAll('.res-checkbox').forEach(checkbox => {
    checkbox.addEventListener('change', (e) => {
        const li = e.target.closest('li');
        if (e.target.checked) {
            li.classList.add('completed'); // durchgestrichen
        } else {
            li.classList.remove('completed');
        }
    });
});



    initSortableList(document.getElementById('todo-list'));
    initSortableList(document.getElementById('res-list'));
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