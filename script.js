const planList = document.getElementById("planList");
const shopList = document.getElementById("shopList");

function addItem(type) {
  const input = document.getElementById(
    type === "plan" ? "planInput" : "shopInput"
  );

  const value = input.value.trim();
  if (!value) return;

  const li = document.createElement("li");
  const span = document.createElement("span");
  span.textContent = value;

  // Abhaken
  span.addEventListener("click", () => {
    li.classList.toggle("done");  
  });

  // Löschen
  const del = document.createElement("button");
  del.textContent = "✕";
  del.className = "delete";
  del.addEventListener("click", () => li.remove());

  li.appendChild(span);
  li.appendChild(del);

  if (type === "plan") {
    planList.appendChild(li);
  } else {
    shopList.appendChild(li);
  }

  input.value = "";
}