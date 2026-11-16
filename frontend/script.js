(async function startAdminPage() {
  const response = await fetch("/api/me");
  if (!response.ok) {
    location.replace("/");
    return;
  }
  const me = await response.json();
  if (me.role !== "admin") {
    location.replace("/home.html");
    return;
  }
  document.getElementById("adminName").textContent = me.name;
  document.getElementById("adminLoginId").textContent = me.login_id;
  document.getElementById("logoutButton").addEventListener("click", async () => {
    await fetch("/api/logout", {method: "POST"});
    location.replace("/");
  });

const defaultTasks = [
  {id: "T001", name: "店舗清掃", points: 2},
  {id: "T002", name: "レジ担当", points: 3},
  {id: "T003", name: "品出し", points: 2},
  {id: "T004", name: "閉店作業", points: 5}
];

let users = [];
let tasks = load("admin_demo_tasks", defaultTasks);
let modalType = null;

function load(key, fallback) {
  try { const saved = localStorage.getItem(key); return saved ? JSON.parse(saved) : fallback; }
  catch { return fallback; }
}
function persist() {
  localStorage.setItem("admin_demo_tasks", JSON.stringify(tasks));
}
function escapeHTML(value) {
  return String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message; toast.classList.remove("hidden");
  clearTimeout(showToast.timer); showToast.timer = setTimeout(() => toast.classList.add("hidden"), 2400);
}
async function refreshUsers() {
  const response = await fetch("/api/admin/users");
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) location.replace("/");
    throw new Error("ユーザー一覧を読み込めませんでした");
  }
  users = await response.json();
  renderUsers();
}
function navigate(page) {
  document.querySelectorAll(".page").forEach(el => el.classList.toggle("active", el.id === `page-${page}`));
  document.querySelectorAll(".nav-item").forEach(el => el.classList.toggle("active", el.dataset.page === page));
  const names = {dashboard:"ダッシュボード",users:"ユーザー管理",tasks:"任務種類の管理"};
  document.getElementById("breadcrumbCurrent").textContent = names[page];
  document.getElementById("sidebar").classList.remove("open");
  if(page === "users") renderUsers();
  if(page === "tasks") renderTasks();
}
document.querySelectorAll("[data-page]").forEach(btn => btn.addEventListener("click", () => navigate(btn.dataset.page)));
document.querySelectorAll("[data-go]").forEach(btn => btn.addEventListener("click", () => navigate(btn.dataset.go)));
document.getElementById("mobileMenu").addEventListener("click", () => document.getElementById("sidebar").classList.toggle("open"));

function updateStats() {
  document.getElementById("userCount").textContent = users.length;
  document.getElementById("taskCount").textContent = tasks.length;
  document.getElementById("userTableCount").textContent = users.length;
  document.getElementById("taskTableCount").textContent = tasks.length;
}
function renderUsers() {
  const query = document.getElementById("userSearch").value.trim().toLowerCase();
  const filtered = users.filter(u => `${u.name} ${u.login_id}`.toLowerCase().includes(query));
  document.getElementById("userTableBody").innerHTML = filtered.map(u => `
    <tr><td><div class="user-cell"><div class="user-avatar">${escapeHTML(u.name.slice(0,1))}</div><div><div class="user-name">${escapeHTML(u.name)}</div><div class="user-sub">登録ユーザー</div></div></div></td>
    <td>${escapeHTML(u.login_id)}</td><td><span class="state">有効</span></td>
    <td class="align-right"><button class="delete-btn" data-delete-user="${u.id}">削除</button></td></tr>`).join("");
  document.getElementById("userEmpty").classList.toggle("hidden", filtered.length !== 0);
  document.getElementById("userTableBody").classList.toggle("hidden", filtered.length === 0);
  updateStats();
}
function renderTasks() {
  const query = document.getElementById("taskSearch").value.trim().toLowerCase();
  const filtered = tasks.filter(t => `${t.name} ${t.id}`.toLowerCase().includes(query));
  document.getElementById("taskTableBody").innerHTML = filtered.map(t => `
    <tr><td><div class="user-cell"><div class="menu-card-icon purple" style="width:31px;height:31px;font-size:15px">☷</div><div><div class="user-name">${escapeHTML(t.name)}</div><div class="user-sub">${escapeHTML(t.id)}</div></div></div></td>
    <td><span class="points">${Number(t.points)} pt</span></td><td><span class="state">有効</span></td>
    <td class="align-right"><button class="delete-btn" data-delete-task="${escapeHTML(t.id)}">削除</button></td></tr>`).join("");
  document.getElementById("taskEmpty").classList.toggle("hidden", filtered.length !== 0);
  document.getElementById("taskTableBody").classList.toggle("hidden", filtered.length === 0);
  updateStats();
}
document.getElementById("userSearch").addEventListener("input", renderUsers);
document.getElementById("taskSearch").addEventListener("input", renderTasks);

function openModal(type) {
  modalType = type;
  const isUser = type === "user";
  document.getElementById("modalEyebrow").textContent = isUser ? "NEW USER" : "NEW TASK";
  document.getElementById("modalTitle").textContent = isUser ? "新規ユーザー登録" : "任務の追加";
  document.getElementById("saveModal").textContent = isUser ? "ユーザーを登録" : "任務を追加";
  document.getElementById("modalFields").innerHTML = isUser ? `
    <div class="field"><label for="entryName">ユーザー名</label><input id="entryName" name="name" maxlength="40" placeholder="例：山田 太郎" required></div>
    <div class="field"><label for="entryId">ユーザーID</label><input id="entryId" name="login_id" maxlength="20" placeholder="例：U005" required><div class="hint">他のユーザーと重複しないIDを入力してください。</div></div>
    <div class="field"><label for="entryPassword">初期パスワード</label><input id="entryPassword" name="password" type="password" minlength="8" maxlength="128" autocomplete="new-password" required><div class="hint">8文字以上で設定してください。ユーザーに安全な方法で伝えてください。</div></div>` : `
    <div class="field"><label for="entryTask">任務名</label><input id="entryTask" name="name" maxlength="40" placeholder="例：備品整理" required></div>
    <div class="field"><label for="entryPoints">ポイント</label><input id="entryPoints" name="points" type="number" min="0" max="999" value="1" required><div class="hint">任務に割り当てるポイントを入力してください。</div></div>`;
  document.getElementById("modalBackdrop").classList.remove("hidden");
  setTimeout(() => document.querySelector("#modalFields input")?.focus(), 50);
}
function closeModal() { document.getElementById("modalBackdrop").classList.add("hidden"); document.getElementById("modalForm").reset(); }
document.getElementById("addUserBtn").addEventListener("click", () => openModal("user"));
document.getElementById("addTaskBtn").addEventListener("click", () => openModal("task"));
document.getElementById("closeModal").addEventListener("click", closeModal);
document.getElementById("cancelModal").addEventListener("click", closeModal);
document.getElementById("modalBackdrop").addEventListener("click", e => { if(e.target.id === "modalBackdrop") closeModal(); });
document.addEventListener("keydown", e => { if(e.key === "Escape") closeModal(); });

document.getElementById("modalForm").addEventListener("submit", async e => {
  e.preventDefault();
  const data = new FormData(e.currentTarget);
  const name = String(data.get("name") || "").trim();
  if(modalType === "user") {
    const loginId = String(data.get("login_id") || "").trim();
    const password = String(data.get("password") || "");
    try {
      const response = await fetch("/api/admin/users", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({login_id: loginId, name, password}),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        showToast(result.detail || "ユーザーを登録できませんでした。");
        return;
      }
      await refreshUsers();
      showToast("ユーザーを登録しました。");
    } catch {
      showToast("サーバーに接続できませんでした。");
      return;
    }
  } else {
    const points = Number(data.get("points"));
    if(!Number.isFinite(points) || points < 0) { showToast("ポイントは0以上で入力してください。"); return; }
    tasks.push({id: nextId("T", tasks), name, points}); persist(); renderTasks(); showToast("任務を追加しました。");
  }
  closeModal();
});
function nextId(prefix, items) {
  let n = items.length + 1, id;
  do { id = `${prefix}${String(n).padStart(3,"0")}`; n++; } while(items.some(x => x.id === id));
  return id;
}
document.addEventListener("click", e => {
  const userId = e.target.dataset.deleteUser;
  const taskId = e.target.dataset.deleteTask;
  if(userId) {
    const target = users.find(u => String(u.id) === userId);
    if(target && confirm(`「${target.name}（${target.login_id}）」を削除しますか？`)) {
      fetch(`/api/admin/users/${userId}`, {method: "DELETE"})
        .then(async response => {
          const result = await response.json().catch(() => ({}));
          if (!response.ok) throw new Error(result.detail || "ユーザーを削除できませんでした。");
          await refreshUsers();
          showToast("ユーザーを削除しました。");
        })
        .catch(error => showToast(error.message || "サーバーに接続できませんでした。"));
    }
  }
  if(taskId) {
    const target = tasks.find(t => t.id === taskId);
    if(target && confirm(`「${target.name}」を削除しますか？`)) {
      tasks = tasks.filter(t => t.id !== taskId); persist(); renderTasks(); showToast("任務を削除しました。");
    }
  }
});

document.getElementById("today").textContent = new Intl.DateTimeFormat("ja-JP",{year:"numeric",month:"long",day:"numeric",weekday:"short"}).format(new Date());
refreshUsers().catch(error => showToast(error.message));
updateStats(); renderTasks();
})();
