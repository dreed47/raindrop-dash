let DATA = [];
let TREE = [];
let activeCollection = null;
let activeTag = null;
let activeFavorites = false;
let expandedCollections = new Set();
const COLORS = [
  "#58a6ff",
  "#f0883e",
  "#a371f7",
  "#3fb950",
  "#f778ba",
  "#79c0ff",
  "#d2a8ff",
  "#56d364",
];

function buildTree(collections) {
  const map = {};
  const roots = [];
  collections.forEach((c) => {
    map[c.id] = { ...c, children: [] };
  });
  collections.forEach((c) => {
    if (c.parent_id != null && map[c.parent_id]) {
      map[c.parent_id].children.push(map[c.id]);
    } else {
      roots.push(map[c.id]);
    }
  });
  return roots;
}

function countTotal(node) {
  return (
    node.bookmarks.length +
    node.children.reduce((s, ch) => s + countTotal(ch), 0)
  );
}

function getCollectionAndDescendants(id) {
  const result = new Set([id]);
  let changed = true;
  while (changed) {
    changed = false;
    DATA.forEach((c) => {
      if (
        c.parent_id != null &&
        result.has(c.parent_id) &&
        !result.has(c.id)
      ) {
        result.add(c.id);
        changed = true;
      }
    });
  }
  return result;
}

function toggleChildren(id) {
  if (expandedCollections.has(id)) {
    expandedCollections.delete(id);
  } else {
    expandedCollections.add(id);
  }
  renderSidebar();
}

function renderCollItem(node, depth, colorIdx) {
  const color = node.color || COLORS[colorIdx % COLORS.length];
  const indent = depth * 14;
  const hasChildren = node.children.length > 0;
  const isExpanded = expandedCollections.has(node.id);
  const total = hasChildren ? countTotal(node) : node.bookmarks.length;
  let html = `<div class="coll-item ${activeCollection === node.id ? "active" : ""}" style="padding-left:${16 + indent}px" onclick="filterCollection(${node.id})">\n`;
  if (hasChildren) {
    html += `<span class="coll-toggle${isExpanded ? " open" : ""}" onclick="event.stopPropagation();toggleChildren(${node.id})"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m9 18 6-6-6-6"/></svg></span>`;
  } else {
    html += `<div class="coll-dot" style="background:${color}"></div>`;
  }
  html += `<span class="coll-name">${esc(node.title)}</span><span class="coll-count">${total}</span></div>`;
  if (hasChildren) {
    html += `<div id="children-${node.id}" class="coll-children${isExpanded ? "" : " collapsed"}">\n`;
    node.children.forEach((child, j) => {
      html += renderCollItem(child, depth + 1, colorIdx + j + 1);
    });
    html += "</div>";
  }
  return html;
}

async function load() {
  try {
    const r = await fetch("/api/bookmarks");
    const j = await r.json();
    if (!j.ok) throw new Error(j.error);
    DATA = j.collections;
    TREE = buildTree(DATA);
    const saved = localStorage.getItem("activeCollection");
    if (saved !== null) {
      const id = saved === "null" ? null : parseInt(saved, 10);
      if (id === null || DATA.some((c) => c.id === id))
        activeCollection = id;
    }
    const coll =
      activeCollection === null
        ? null
        : DATA.find((c) => c.id === activeCollection);
    document.title = coll ? coll.title : "Bookmarks";
    renderSidebar();
    renderMain();
    updateStats();
  } catch (e) {
    document.getElementById("main").innerHTML =
      `<div class="error-state">Error: ${e.message}</div>`;
  }
}

async function refresh() {
  const btn = document.getElementById("refreshBtn");
  btn.classList.add("spinning");
  try {
    const r = await fetch("/api/refresh", { method: "POST" });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error);
    DATA = j.collections;
    TREE = buildTree(DATA);
    renderSidebar();
    renderMain();
    updateStats();
    showToast("Bookmarks refreshed");
  } catch (e) {
    showToast("Refresh failed: " + e.message, "error");
  } finally {
    btn.classList.remove("spinning");
  }
}

function openDrawer() {
  document.getElementById("sidebarDrawer").classList.add("open");
  document.getElementById("drawerOverlay").classList.add("open");
}

function closeDrawer() {
  document.getElementById("sidebarDrawer").classList.remove("open");
  document.getElementById("drawerOverlay").classList.remove("open");
}

function renderSidebar() {
  // Collections section
  let html = '<div class="sidebar-label">Collections</div>';
  const totalAll = DATA.reduce((s, c) => s + c.bookmarks.length, 0);
  const totalFavs = [
    ...new Map(
      DATA.flatMap((c) => c.bookmarks).map((b) => [b.id, b]),
    ).values(),
  ].filter((b) => b.important).length;
  html += `<div class="coll-item ${activeCollection === null && !activeTag && !activeFavorites ? "active" : ""}" onclick="filterCollection(null)">
<div class="coll-dot" style="background:#8b949e"></div>
<span class="coll-name">All</span>
<span class="coll-count">${totalAll}</span>
    </div>`;
  html += `<div class="coll-item ${activeFavorites ? "active" : ""}" onclick="filterFavorites()">
<div class="coll-dot" style="background:#e3b341"></div>
<span class="coll-name">&#9829; Favorites</span>
<span class="coll-count">${totalFavs}</span>
    </div>`;
  TREE.forEach((node, i) => {
    html += renderCollItem(node, 0, i);
  });

  // Tags section — deduplicate by bookmark ID first, exclude Unsorted collection
  const seenIds = new Set();
  const tagMap = {};
  DATA.forEach((c) => {
    if (c.id === -1) return; // skip Unsorted
    c.bookmarks.forEach((b) => {
      if (seenIds.has(b.id)) return;
      seenIds.add(b.id);
      b.tags.forEach((t) => {
        tagMap[t] = (tagMap[t] || 0) + 1;
      });
    });
  });
  const tags = Object.keys(tagMap).sort();
  if (tags.length) {
    html +=
      '<div class="sidebar-label" style="margin-top:8px">Tags</div>';
    tags.forEach((t) => {
      html += `<div class="coll-item sidebar-tag${activeTag === t ? " active" : ""}" data-tag="${esc(t)}">
    <span class="coll-name">#${esc(t)}</span>
    <span class="coll-count">${tagMap[t]}</span>
  </div>`;
    });
  }

  document.getElementById("sidebarCollections").innerHTML = html;
  document.getElementById("drawerContent").innerHTML = html;
}

function renderMain() {
  const q = document.getElementById("search").value.toLowerCase().trim();
  const main = document.getElementById("main");
  const filtered =
    activeCollection === null
      ? DATA
      : DATA.filter((c) => c.id === activeCollection);

  let html = "";
  let total = 0;
  filtered.forEach((coll) => {
    let bms = coll.bookmarks;
    if (activeFavorites) {
      bms = bms.filter((b) => b.important);
    }
    if (activeTag) {
      bms = bms.filter((b) => b.tags.includes(activeTag));
    }
    if (q) {
      bms = bms.filter(
        (b) =>
          b.title.toLowerCase().includes(q) ||
          b.domain.toLowerCase().includes(q) ||
          b.excerpt.toLowerCase().includes(q) ||
          (b.note || "").toLowerCase().includes(q) ||
          b.tags.some((t) => t.toLowerCase().includes(q)),
      );
    }
    if (!bms.length) return;
    total += bms.length;
    html += `<div class="collection-group" id="coll-${coll.id}">
  <div class="collection-title">${esc(coll.title)} <span class="count">${bms.length}</span></div>
  <div class="bookmarks-grid">`;
    bms.forEach((b) => {
      const favicon = `https://www.google.com/s2/favicons?domain=${encodeURIComponent(b.domain)}&sz=32`;
      html += `<a class="bm-card" href="${esc(b.link)}" target="_blank" rel="noopener">
    <button class="bm-edit" onclick="event.preventDefault();event.stopPropagation();openEditModal(${b.id})" aria-label="Edit bookmark" title="Edit">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
    </button>
    <button class="bm-delete" onclick="event.preventDefault();event.stopPropagation();deleteBookmark(${b.id}, this)" aria-label="Delete bookmark" title="Delete">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
    </button>
    <img class="bm-favicon" src="${favicon}" alt="" loading="lazy" onerror="this.style.display='none'">
    <div class="bm-body">
      <div class="bm-title">${esc(b.title)}</div>
      <div class="bm-domain">${b.important ? '<span class="bm-important">&#9829;</span> ' : ""}${esc(b.domain)}</div>
      ${b.excerpt ? `<div class="bm-excerpt">${esc(b.excerpt)}</div>` : ""}
      ${b.note ? `<div class="bm-note">${esc(b.note)}</div>` : ""}
      ${b.tags.length ? `<div class="bm-tags">${b.tags.map((t) => `<span class="bm-tag${activeTag === t ? " active-tag" : ""}" data-tag="${esc(t)}">${esc(t)}</span>`).join("")}</div>` : ""}
      ${(b.highlights && b.highlights.length) || b.created ? `<div class="bm-meta">${b.highlights && b.highlights.length ? `<div class="bm-highlights">${b.highlights.map((c) => `<span class="bm-hl" style="--hl-color:${hlColor(c)}"></span>`).join("")}</div>` : ""}${b.created ? `<span class="bm-date">${fmtDate(b.created)}</span>` : ""}</div>` : ""}
    </div>
  </a>`;
    });
    html += "</div></div>";
  });

  if (!html) html = '<div class="empty-msg">No bookmarks found.</div>';
  main.innerHTML = html;
}

function filterFavorites() {
  activeFavorites = true;
  activeCollection = null;
  activeTag = null;
  document.getElementById("tagFilterBar").classList.remove("visible");
  localStorage.setItem("activeCollection", "null");
  document.title = "Bookmarks";
  closeDrawer();
  renderSidebar();
  renderMain();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function filterCollection(id) {
  activeFavorites = false;
  activeTag = null;
  document.getElementById("tagFilterBar").classList.remove("visible");
  activeCollection = id;
  localStorage.setItem("activeCollection", id === null ? "null" : id);
  const coll = id === null ? null : DATA.find((c) => c.id === id);
  document.title = coll ? coll.title : "Bookmarks";
  closeDrawer();
  renderSidebar();
  renderMain();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function filterTag(tag) {
  if (activeTag === tag) {
    clearTagFilter();
    return;
  }
  activeTag = tag;
  activeFavorites = false;
  // Always search across all collections so count matches sidebar
  activeCollection = null;
  localStorage.setItem("activeCollection", "null");
  document.title = "Bookmarks";
  document.getElementById("tagFilterLabel").textContent = tag;
  document.getElementById("tagFilterBar").classList.add("visible");
  renderSidebar();
  renderMain();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function clearTagFilter() {
  activeTag = null;
  activeFavorites = false;
  document.getElementById("tagFilterBar").classList.remove("visible");
  renderSidebar();
  renderMain();
}

function updateStats() {
  const total = DATA.reduce((s, c) => s + c.bookmarks.length, 0);
  document.getElementById("stats").textContent =
    `${DATA.length} collections · ${total} bookmarks`;
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s || "";
  return d.innerHTML;
}

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

const HL_COLORS = {
  yellow: "#ffd60a",
  blue: "#58a6ff",
  green: "#3fb950",
  red: "#f85149",
  orange: "#f0883e",
  pink: "#db61a2",
  purple: "#bc8cff",
};

function hlColor(name) {
  return HL_COLORS[name] || "#8b949e";
}

// Tag click — event delegation on the main area and sidebar
document.addEventListener("click", (e) => {
  const tagEl = e.target.closest("[data-tag]");
  if (!tagEl) return;
  e.preventDefault();
  e.stopPropagation();
  filterTag(tagEl.dataset.tag);
});

// Debounced search
let _st;
document.getElementById("search").addEventListener("input", () => {
  clearTimeout(_st);
  _st = setTimeout(renderMain, 200);
});

// Keyboard shortcut: / to focus search
document.addEventListener("keydown", (e) => {
  if (e.key === "/" && document.activeElement.tagName !== "INPUT") {
    e.preventDefault();
    document.getElementById("search").focus();
  }
});

let _toastTimer;
function showToast(msg, type = "success") {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = `toast ${type}`;
  // Force reflow so transition fires even on rapid successive calls
  t.getBoundingClientRect();
  t.classList.add("show");
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => t.classList.remove("show"), 3000);
}

// --- Edit bookmark modal ---
let _editId = null;
let _editOrigCollId = null;

function openEditModal(id) {
  // Find bookmark and its parent collection from loaded DATA
  let bm = null;
  let collId = "";
  for (const c of DATA) {
    const found = c.bookmarks.find((b) => b.id === id);
    if (found) {
      bm = found;
      collId = c.id === -1 || c.id === 0 ? "" : String(c.id);
      break;
    }
  }
  if (!bm) return;
  _editId = id;
  _editOrigCollId = collId;

  const sel = document.getElementById("editCollection");
  sel.innerHTML = '<option value="">Unsorted</option>';
  DATA.forEach((c) => {
    if (c.id === -1) return; // Unsorted already listed
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.title;
    sel.appendChild(opt);
  });
  sel.value = collId;

  document.getElementById("editUrl").value = bm.link || "";
  document.getElementById("editTitle").value = bm.title || "";
  document.getElementById("editTags").value = (bm.tags || []).join(", ");
  document.getElementById("editNote").value = bm.note || "";
  document.getElementById("editImportant").checked = !!bm.important;
  document.getElementById("editError").className = "modal-error";
  document.getElementById("editSaveBtn").disabled = false;
  document.getElementById("editSaveBtn").textContent = "Save";
  document.getElementById("editModal").classList.add("open");
  setTimeout(() => document.getElementById("editTitle").focus(), 50);
}

function closeEditModal() {
  document.getElementById("editModal").classList.remove("open");
  _editId = null;
  _editOrigCollId = null;
}

async function saveEdit() {
  const url = document.getElementById("editUrl").value.trim();
  if (!url) {
    const el = document.getElementById("editError");
    el.textContent = "URL is required.";
    el.className = "modal-error visible";
    return;
  }
  const btn = document.getElementById("editSaveBtn");
  btn.disabled = true;
  btn.textContent = "Saving…";
  document.getElementById("editError").className = "modal-error";
  try {
    const newCollId =
      document.getElementById("editCollection").value || null;
    const body = {
      link: url,
      title: document.getElementById("editTitle").value.trim(),
      tags: document.getElementById("editTags").value,
      note: document.getElementById("editNote").value.trim(),
      important: document.getElementById("editImportant").checked,
    };
    // Only send collection_id if it actually changed — sending it unconditionally
    // causes Raindrop to reset the bookmark's sort position to the top.
    const origVal = _editOrigCollId || null;
    if (newCollId !== origVal) body.collection_id = newCollId;

    const r = await fetch(`/api/edit/${_editId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error);
    closeEditModal();
    showToast("Bookmark saved");
    // Refresh server cache and update UI
    try {
      const rb = document.getElementById("refreshBtn");
      if (rb) rb.classList.add("spinning");
      const rr = await fetch("/api/refresh", { method: "POST" });
      const rj = await rr.json();
      if (rj.ok) {
        DATA = rj.collections;
        TREE = buildTree(DATA);
      }
      if (rb) rb.classList.remove("spinning");
    } catch (_) {}
    // Always re-render UI after a successful edit
    renderSidebar();
    renderMain();
    updateStats();
  } catch (err) {
    const el = document.getElementById("editError");
    el.textContent = err.message;
    el.className = "modal-error visible";
    btn.disabled = false;
    btn.textContent = "Save";
  }
}

// --- Add bookmark modal ---
function openAddModal() {
  // Populate collection dropdown from loaded data
  const sel = document.getElementById("addCollection");
  sel.innerHTML = '<option value="">Unsorted</option>';
  DATA.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.title;
    if (activeCollection !== null && c.id === activeCollection)
      opt.selected = true;
    sel.appendChild(opt);
  });
  document.getElementById("addUrl").value = "";
  document.getElementById("addTitle").value = "";
  document.getElementById("addTags").value = "";
  document.getElementById("addImportant").checked = false;
  document.getElementById("addError").className = "modal-error";
  document.getElementById("addSaveBtn").disabled = false;
  document.getElementById("addModal").classList.add("open");
  setTimeout(() => document.getElementById("addUrl").focus(), 50);
}

function closeAddModal() {
  document.getElementById("addModal").classList.remove("open");
}

function handleModalBackdropClick(e) {
  if (e.target === document.getElementById("addModal")) closeAddModal();
}

async function saveBookmark() {
  const url = document.getElementById("addUrl").value.trim();
  if (!url) {
    showAddError("URL is required.");
    return;
  }
  const btn = document.getElementById("addSaveBtn");
  btn.disabled = true;
  btn.textContent = "Saving…";
  document.getElementById("addError").className = "modal-error";
  try {
    const r = await fetch("/api/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        link: url,
        title: document.getElementById("addTitle").value.trim(),
        tags: document.getElementById("addTags").value,
        collection_id:
          document.getElementById("addCollection").value || null,
        important: document.getElementById("addImportant").checked,
      }),
    });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error);
    closeAddModal();
    showToast("Bookmark added");
    // Refresh data so the new bookmark appears
    const rb = document.getElementById("refreshBtn");
    rb.classList.add("spinning");
    const rr = await fetch("/api/refresh", { method: "POST" });
    const rj = await rr.json();
    if (rj.ok) {
      DATA = rj.collections;
      TREE = buildTree(DATA);
      renderSidebar();
      renderMain();
      updateStats();
    }
    rb.classList.remove("spinning");
  } catch (e) {
    showAddError(e.message);
    btn.disabled = false;
    btn.textContent = "Save";
  }
}

function showAddError(msg) {
  const el = document.getElementById("addError");
  el.textContent = msg;
  el.className = "modal-error visible";
}

async function deleteBookmark(id, btn) {
  if (!confirm("Delete this bookmark? This cannot be undone.")) return;
  btn.disabled = true;
  try {
    const r = await fetch(`/api/remove/${id}`, { method: "DELETE" });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error);
    // Remove card from DOM immediately without a full reload
    const card = btn.closest(".bm-card");
    const grid = card.closest(".bookmarks-grid");
    const group = card.closest(".collection-group");
    card.remove();
    showToast("Bookmark deleted");
    // Also remove from DATA so counts stay accurate
    DATA.forEach((c) => {
      c.bookmarks = c.bookmarks.filter((b) => b.id !== id);
    });
    if (!grid.children.length) group.remove();
    updateStats();
    renderSidebar();
  } catch (e) {
    alert("Delete failed: " + e.message);
    btn.disabled = false;
  }
}

async function checkStatus() {
  try {
    const r = await fetch("/api/status");
    const j = await r.json();
    if (!j.token_set) {
      showToast(
        "RAINDROP_TOKEN not set — bookmarks will not load",
        "error",
      );
    } else if (!j.redis_connected) {
      showToast("Redis unavailable — using in-memory cache", "warning");
    }
  } catch (_) {
    // status check is non-critical, ignore failures
  }
}

load();
checkStatus();
