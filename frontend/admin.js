const $ = (id) => document.getElementById(id);
let me = null;
let users = [];
let tasks = [];
let modalType = null;

async function api(path, options = {}) {
    const response = await fetch(path, {
        ...options,
        headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...options.headers },
    });
    if (response.status === 401) { location.replace("/"); throw new Error("ログインしてください"); }
    if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(typeof body.detail === "string" ? body.detail : "入力内容を確認してください");
    }
    return response.status === 204 ? null : response.json();
}

function toast(message, isError = false) {
    const node = $("toast");
    node.textContent = message;
    node.classList.toggle("error", isError);
    node.classList.remove("hidden");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => node.classList.add("hidden"), 3000);
}

function showPage(page) {
    document.querySelectorAll(".page").forEach((node) => node.classList.toggle("active", node.id === `page-${page}`));
    document.querySelectorAll(".nav-item").forEach((node) => node.classList.toggle("active", node.dataset.page === page));
    const labels = { dashboard: "ダッシュボード", users: "ユーザー管理", tasks: "任務種類の管理" };
    $("breadcrumbCurrent").textContent = labels[page];
    history.replaceState(null, "", `#${page}`);
    $("sidebar").classList.remove("open");
}

// 「有効」「無効」の表示
function statusCell(isActive) {
    const cell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = isActive ? "status-badge active" : "status-badge inactive";
    badge.textContent = isActive ? "有効" : "無効";
    cell.append(badge);
    return cell;
}

// 有効なら「無効にする」、無効なら「有効にする」ボタン
function toggleButton(isActive, onClick) {
    const button = document.createElement("button");
    button.className = isActive ? "deactivate-btn" : "activate-btn";
    button.textContent = isActive ? "無効にする" : "有効にする";
    button.addEventListener("click", onClick);
    return button;
}

function renderUsers() {
    const query = $("userSearch").value.trim().toLocaleLowerCase();
    const showInactive = $("userShowInactive").checked;
    const filtered = users.filter((user) =>
        (showInactive || user.is_active) &&
        `${user.name} ${user.login_id}`.toLocaleLowerCase().includes(query));
    $("userTableCount").textContent = filtered.length;
    $("userTableBody").replaceChildren();
    $("userEmpty").classList.toggle("hidden", filtered.length > 0);
    for (const user of filtered) {
        const row = document.createElement("tr");
        if (!user.is_active) row.className = "inactive";
        const identity = document.createElement("td");
        identity.innerHTML = `<div class="user-cell"><span class="user-avatar"></span><strong></strong></div>`;
        identity.querySelector(".user-avatar").textContent = user.name.slice(0, 1);
        identity.querySelector("strong").textContent = user.name;
        const login = document.createElement("td"); login.textContent = user.login_id;
        const status = statusCell(user.is_active);
        const actions = document.createElement("td"); actions.className = "align-right";
        // 自分自身は無効にできないので、ボタンを出さない
        if (user.id !== me.id) actions.append(toggleButton(user.is_active, () => setUserActive(user, !user.is_active)));
        row.append(identity, login, status, actions); $("userTableBody").append(row);
    }
    $("userCount").textContent = users.filter((user) => user.is_active).length;
}

function renderTasks() {
    const query = $("taskSearch").value.trim().toLocaleLowerCase();
    const showInactive = $("taskShowInactive").checked;
    const filtered = tasks.filter((task) =>
        (showInactive || task.is_active) && task.name.toLocaleLowerCase().includes(query));
    $("taskTableCount").textContent = filtered.length;
    $("taskTableBody").replaceChildren();
    $("taskEmpty").classList.toggle("hidden", filtered.length > 0);
    for (const task of filtered) {
        const row = document.createElement("tr");
        if (!task.is_active) row.className = "inactive";
        const name = document.createElement("td"); name.textContent = task.name;
        const points = document.createElement("td"); points.textContent = `${task.points} pt`;
        const status = statusCell(task.is_active);
        const actions = document.createElement("td"); actions.className = "align-right";
        actions.append(toggleButton(task.is_active, () => setTaskActive(task, !task.is_active)));
        row.append(name, points, status, actions); $("taskTableBody").append(row);
    }
    $("taskCount").textContent = tasks.filter((task) => task.is_active).length;
}

async function refresh() {
    [users, tasks] = await Promise.all([api("/api/users"), api("/api/tasks")]);
    renderUsers(); renderTasks();
}

function openModal(type) {
    modalType = type;
    const userMode = type === "user";
    $("modalEyebrow").textContent = userMode ? "NEW USER" : "NEW TASK";
    $("modalTitle").textContent = userMode ? "新規ユーザー" : "任務を追加";
    $("saveModal").textContent = userMode ? "ユーザーを登録" : "任務を登録";
    const fields = $("modalFields"); fields.replaceChildren();
    const definitions = userMode
        ? [["name", "表示名", "text", "例: 山田 太郎"], ["login_id", "ユーザーID", "text", "ログインに使うID"], ["password", "初期パスワード", "password", "8文字以上"]]
        : [["name", "任務名", "text", "例: 共有スペースの清掃"], ["points", "ポイント", "number", "1以上"]];
    for (const [id, label, inputType, placeholder] of definitions) {
        const wrap = document.createElement("div"); wrap.className = "field";
        const caption = document.createElement("label"); caption.htmlFor = `field-${id}`; caption.textContent = label;
        const input = document.createElement("input"); input.id = `field-${id}`; input.name = id; input.type = inputType; input.placeholder = placeholder; input.required = true;
        if (id === "password") input.minLength = 8;
        if (id === "points") { input.min = "1"; input.step = "1"; input.value = "1"; }
        wrap.append(caption, input);
        if (id === "password") { const note = document.createElement("small"); note.textContent = "ログイン時に使用するパスワードです。"; wrap.append(note); }
        fields.append(wrap);
    }
    $("formError").textContent = "";
    $("modalBackdrop").classList.remove("hidden");
    fields.querySelector("input")?.focus();
}

function closeModal() { $("modalBackdrop").classList.add("hidden"); $("modalForm").reset(); }

async function setUserActive(user, isActive) {
    if (!isActive && !confirm(`「${user.name}」を無効にしますか？\nこのユーザーはログインできなくなります。`)) return;
    try {
        await api(`/api/users/${user.id}`, { method: "PATCH", body: JSON.stringify({ is_active: isActive }) });
        await refresh();
        toast(isActive ? "ユーザーを有効にしました" : "ユーザーを無効にしました");
    } catch (error) { toast(error.message, true); }
}

async function setTaskActive(task, isActive) {
    if (!isActive && !confirm(`「${task.name}」を無効にしますか？`)) return;
    try {
        await api(`/api/tasks/${task.id}`, { method: "PATCH", body: JSON.stringify({ is_active: isActive }) });
        await refresh();
        toast(isActive ? "任務を有効にしました" : "任務を無効にしました");
    } catch (error) { toast(error.message, true); }
}

document.querySelectorAll("[data-page]").forEach((button) => button.addEventListener("click", () => showPage(button.dataset.page)));
document.querySelectorAll("[data-go]").forEach((button) => button.addEventListener("click", () => showPage(button.dataset.go)));
$("mobileMenu").addEventListener("click", () => $("sidebar").classList.toggle("open"));
$("userSearch").addEventListener("input", renderUsers);
$("taskSearch").addEventListener("input", renderTasks);
$("userShowInactive").addEventListener("change", renderUsers);
$("taskShowInactive").addEventListener("change", renderTasks);
$("addUserBtn").addEventListener("click", () => openModal("user"));
$("addTaskBtn").addEventListener("click", () => openModal("task"));
$("closeModal").addEventListener("click", closeModal);
$("cancelModal").addEventListener("click", closeModal);
$("modalBackdrop").addEventListener("click", (event) => { if (event.target === $("modalBackdrop")) closeModal(); });
$("modalForm").addEventListener("submit", async (event) => {
    event.preventDefault(); $("saveModal").disabled = true; $("formError").textContent = "";
    const values = Object.fromEntries(new FormData(event.currentTarget));
    if (modalType === "task") values.points = Number(values.points);
    try {
        await api(modalType === "user" ? "/api/users" : "/api/tasks", { method: "POST", body: JSON.stringify(values) });
        closeModal(); await refresh(); toast(modalType === "user" ? "ユーザーを登録しました" : "任務を登録しました");
    } catch (error) { $("formError").textContent = error.message; }
    finally { $("saveModal").disabled = false; }
});
$("logoutButton").addEventListener("click", async () => { await fetch("/api/logout", { method: "POST" }); location.replace("/"); });

async function initialize() {
    try {
        const response = await fetch("/api/me");
        if (!response.ok) { location.replace("/"); return; }
        me = await response.json();
        if (me.role !== "admin") { location.replace("/home.html"); return; }
        document.querySelector(".admin-card strong").textContent = me.name;
        document.querySelector(".admin-card small").textContent = me.login_id;
        $("today").textContent = new Date().toLocaleDateString("ja-JP", { year: "numeric", month: "long", day: "numeric", weekday: "short" });
        await refresh();
        document.querySelector("#page-dashboard").classList.add("active");
        const initial = location.hash.slice(1);
        if (["dashboard", "users", "tasks"].includes(initial)) showPage(initial);
    } catch (error) { toast(error.message, true); }
}
initialize();
