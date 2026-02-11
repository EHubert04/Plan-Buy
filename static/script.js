let currentProjectId = null;
let allProjects = [];
let supabaseClient = null;
let accessToken = null;

function setAuthUI(loggedIn) {
  document.body.classList.toggle('logged-out', !loggedIn);
  document.getElementById('auth-overlay').style.display = loggedIn ? 'none' : 'flex';
  document.getElementById('side-nav').style.display = loggedIn ? 'block' : 'none';
  
  const newBtn = document.querySelector('.btn-new-project');
  if (newBtn) newBtn.style.display = loggedIn ? 'block' : 'none';
}

async function apiFetch(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!headers['Content-Type'] && options.method && options.method !== 'GET') {
    headers['Content-Type'] = 'application/json';
  }
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }
  return fetch(url, { ...options, headers });
}

async function initAuth() {
  supabaseClient = window.supabase.createClient(window.SUPABASE_URL, window.SUPABASE_KEY);

  const { data } = await supabaseClient.auth.getSession();
  accessToken = data?.session?.access_token ?? null;

  setAuthUI(!!accessToken);
  if (accessToken) loadData();

  supabaseClient.auth.onAuthStateChange((_event, session) => {
    accessToken = session?.access_token ?? null;
    setAuthUI(!!accessToken);
    if (accessToken) loadData();
  });
}

async function signUp() {
  const email = document.getElementById('auth-email').value.trim();
  const password = document.getElementById('auth-password').value;
  const msg = document.getElementById('auth-msg');

  const { error, data } = await supabaseClient.auth.signUp({ email, password });
  if (error) { msg.textContent = error.message; return; }
  msg.textContent = data?.session ? "Eingeloggt." : "Bitte E-Mail bestätigen.";
}

async function signIn() {
  const email = document.getElementById('auth-email').value.trim();
  const password = document.getElementById('auth-password').value;
  const { error } = await supabaseClient.auth.signInWithPassword({ email, password });
  if (error) document.getElementById('auth-msg').textContent = error.message;
}

async function signOut() {
  await supabaseClient.auth.signOut();
}

async function loadData() {
  const res = await apiFetch('/api/projects');
  if (!res.ok) {
    console.error("Fehler beim Laden:", await res.text());
    return;
  }
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
  const res = await apiFetch('/api/projects', { 
    method: 'POST', 
    body: JSON.stringify({ name }) 
  });
  if (res.ok) loadData();
}

async function shareCurrentProject() {
  if (!currentProjectId) return;
  const email = prompt("E-Mail des Users:");
  if (!email) return;

  const resp = await apiFetch(`/api/projects/${currentProjectId}/members`, {
    method: 'POST',
    body: JSON.stringify({ email })
  });
  alert(resp.ok ? "User eingeladen." : "Fehler: " + await resp.text());
}

function openProject(id) {
  const project = allProjects.find(p => String(p.id) === String(id));
  if (!project) return;

  currentProjectId = project.id;
  document.getElementById('dashboard').style.display = 'none';
  document.getElementById('project-detail').style.display = 'block';
  document.getElementById('detail-title').innerText = project.name;

  document.getElementById('todo-list').innerHTML = project.todos.map(todo => `
    <li class="${todo.done ? 'completed' : ''}">
      <label>
        <input type="checkbox" class="todo-toggle" data-id="${todo.id}" ${todo.done ? 'checked' : ''}>
        <span>${todo.content}</span>
      </label>
      <button class="btn-delete" data-id="${todo.id}" data-type="todo">🗑️</button>
    </li>`).join('');

  document.getElementById('res-list').innerHTML = project.resources.map(res => `
    <li class="${res.purchased ? 'completed' : ''}">
      <span>${res.name} ${res.category ? `<small>(${res.category})</small>` : ''}</span>
      <input type="number" class="res-qty" value="${res.quantity || 1}" min="1" data-id="${res.id}">
      <input type="checkbox" class="res-toggle" data-id="${res.id}" ${res.purchased ? 'checked' : ''}>
      <button class="btn-delete" data-id="${res.id}" data-type="resource">🗑️</button>
    </li>`).join('');

  setupEventListeners(project);
}

function setupEventListeners(project) {
  // Checkboxen für To-Dos
  document.querySelectorAll('.todo-toggle').forEach(cb => {
    cb.onchange = async (e) => {
      const done = e.target.checked;
      const res = await apiFetch(`/api/projects/${currentProjectId}/todos/${cb.dataset.id}`, {
        method: 'PATCH', body: JSON.stringify({ done })
      });
      if (res.ok) {
        const t = project.todos.find(x => String(x.id) === cb.dataset.id);
        if (t) t.done = done;
        openProject(currentProjectId);
      }
    };
  });

  // Checkboxen für Ressourcen
  document.querySelectorAll('.res-toggle').forEach(cb => {
    cb.onchange = async (e) => {
      const purchased = e.target.checked;
      const res = await apiFetch(`/api/projects/${currentProjectId}/resources/${cb.dataset.id}`, {
        method: 'PATCH', body: JSON.stringify({ purchased })
      });
      if (res.ok) {
        const r = project.resources.find(x => String(x.id) === cb.dataset.id);
        if (r) r.purchased = purchased;
        openProject(currentProjectId);
      }
    };
  });

  // Mengenänderung
  document.querySelectorAll('.res-qty').forEach(inp => {
    inp.onchange = async (e) => {
      const quantity = parseInt(e.target.value) || 1;
      await apiFetch(`/api/projects/${currentProjectId}/resources/${inp.dataset.id}`, {
        method: 'PATCH', body: JSON.stringify({ quantity })
      });
    };
  });

  // Löschen
  document.querySelectorAll('.btn-delete').forEach(btn => {
    btn.onclick = async () => {
      if (!confirm("Löschen?")) return;
      const endpoint = btn.dataset.type === 'todo' ? 'todos' : 'resources';
      const res = await apiFetch(`/api/projects/${currentProjectId}/${endpoint}/${btn.dataset.id}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        await loadData();
        openProject(currentProjectId);
      }
    };
  });
}

async function saveItem(type) {
  const input = document.getElementById(type === 'todo' ? 'todo-input' : 'res-input');
  const content = input.value.trim();
  if (!content) return;

  const resp = await apiFetch(`/api/projects/${currentProjectId}/items`, {
    method: 'POST',
    body: JSON.stringify({ type, content })
  });

  if (resp.ok) {
    const updated = await resp.json();
    const idx = allProjects.findIndex(p => String(p.id) === String(updated.id));
    if (idx >= 0) allProjects[idx] = updated;
    input.value = '';
    renderUI();
    openProject(updated.id);
  }
}

function showDashboard() {
  document.getElementById('dashboard').style.display = 'block';
  document.getElementById('project-detail').style.display = 'none';
}

initAuth();