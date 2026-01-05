function showSection(sectionId) {
    // Alle Sektionen ausblenden
    document.querySelectorAll('.section').forEach(s => s.style.display = 'none');
    // Gewünschte Sektion anzeigen
    document.getElementById(sectionId).style.display = 'block';
}

async function addItem(type) {
    const input = document.getElementById(`${type}-input`);
    const val = input.value;
    
    if (!val) return;

    // An Python Backend senden
    await fetch('http://127.0.0.1:5000/add_item', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ item: val, category: type === 'task' ? 'tasks' : 'resources' })
    });

    input.value = '';
    loadData(); // Liste aktualisieren
}

async function loadData() {
    const response = await fetch('http://127.0.0.1:5000/get_data');
    const result = await response.json();
    
    // Listen im HTML füllen (Beispiel für Tasks)
    const taskList = document.getElementById('task-list');
    taskList.innerHTML = result.tasks.map(t => `<li>${t}</li>`).join('');
    
    const resList = document.getElementById('resource-list');
    resList.innerHTML = result.resources.map(r => `<li>${r}</li>`).join('');
}

// Initial laden
loadData();