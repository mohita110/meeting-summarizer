// If you serve the frontend separately from the backend, set the full backend URL here.
// If FastAPI is serving this frontend directly (StaticFiles mount), relative paths work as-is.
const API_BASE = ""; // e.g. "http://localhost:8000" if hosted separately

const fileInput = document.getElementById("fileInput");
const chooseBtn = document.getElementById("chooseBtn");
const uploadBtn = document.getElementById("uploadBtn");
const fileNameEl = document.getElementById("fileName");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");

let selectedFile = null;

chooseBtn.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
  if (fileInput.files.length > 0) {
    selectedFile = fileInput.files[0];
    fileNameEl.textContent = selectedFile.name;
    uploadBtn.disabled = false;
  }
});

uploadBtn.addEventListener("click", async () => {
  if (!selectedFile) return;

  uploadBtn.disabled = true;
  statusEl.textContent = "Uploading and processing... this can take a minute for longer recordings.";
  resultEl.classList.add("hidden");

  const formData = new FormData();
  formData.append("file", selectedFile);

  try {
    const res = await fetch(`${API_BASE}/api/meetings/upload`, {
      method: "POST",
      body: formData,
    });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Upload failed");
    }

    if (data.status === "failed") {
      statusEl.textContent = `Processing failed: ${data.error}`;
    } else {
      statusEl.textContent = "Done!";
      renderResult(data);
      loadHistory();
    }
  } catch (err) {
    statusEl.textContent = `Error: ${err.message}`;
  } finally {
    uploadBtn.disabled = false;
  }
});

function renderResult(data) {
  document.getElementById("summaryText").textContent = data.summary || "(no summary)";

  const decisionsList = document.getElementById("decisionsList");
  decisionsList.innerHTML = "";
  (data.key_decisions || []).forEach((d) => {
    const li = document.createElement("li");
    li.textContent = d;
    decisionsList.appendChild(li);
  });

  const actionBody = document.getElementById("actionBody");
  actionBody.innerHTML = "";
  (data.action_items || []).forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `<td>${escapeHtml(item.task)}</td><td>${escapeHtml(item.owner)}</td><td>${escapeHtml(item.due_date)}</td>`;
    actionBody.appendChild(row);
  });

  document.getElementById("transcriptText").textContent = data.transcript || "";
  resultEl.classList.remove("hidden");
}

async function loadHistory() {
  try {
    const res = await fetch(`${API_BASE}/api/meetings`);
    const meetings = await res.json();
    const list = document.getElementById("historyList");
    list.innerHTML = "";
    meetings.forEach((m) => {
      const li = document.createElement("li");
      li.textContent = `${m.filename} — ${m.status} — ${new Date(m.created_at).toLocaleString()}`;
      li.addEventListener("click", () => renderResult(m));
      list.appendChild(li);
    });
  } catch (err) {
    console.error("Could not load history", err);
  }
}

function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// Load history on page load
loadHistory();
