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

    document.getElementById('todo-list').innerHTML = project.todos.map(i => `<li>${i}</li>`).join('');
    document.getElementById('res-list').innerHTML = project.resources.map(i => `<li>${i}</li>`).join('');
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

loadData();