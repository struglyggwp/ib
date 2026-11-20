"use strict";

const main = document.getElementById("main");
const shell = document.getElementById("shell");
const auth = document.getElementById("auth");
const dialog = document.getElementById("overlay");
const notice = document.getElementById("toast");
const menu = document.getElementById("menu-toggle");
const sidebar = document.getElementById("sidebar");
const backdrop = document.getElementById("menu-backdrop");

const adminPages = {
  overview: ["Обзор", "grid"],
  campaigns: ["Кампании", "campaign"],
  participants: ["Сотрудники", "users"],
  scenarios: ["Сценарии", "layers"],
  mail: ["Почта", "inbox"],
};
const learnerPages = { lessons: ["Мои задания", "list"] };
const theme = {
  gov: ["building", "blue"], hr: ["list", "purple"], it: ["shield", "mint"], delivery: ["delivery", "amber"],
};
const mailLabels = {
  pending: ["Ожидает отправки", "neutral"],
  sending: ["Отправляется", "neutral"],
  accepted: ["Принято Zimbra", "live"],
  rejected: ["Ошибка SMTP", "review"],
  unknown: ["Статус неизвестен", "review"],
};
const ui = { account: null, data: null, page: "", campaign: null, search: "", lesson: null, busy: false };
const formatter = new Intl.DateTimeFormat("ru-RU", {
  dateStyle: "short", timeStyle: "short", timeZone: "Europe/Moscow",
});
let toastTimer;

function esc(value) {
  const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return String(value ?? "").replace(/[&<>"']/g, (char) => entities[char]);
}

function icon(name) {
  return `<span class="icon i-${name}" aria-hidden="true"></span>`;
}

function tile(name, tone = "mint") {
  return `<span class="tile-icon tone-${tone}">${icon(name)}</span>`;
}

function button(text, action, { kind = "primary", symbol, id, compact = false } = {}) {
  return `<button type="button" class="button button-${kind} ${compact ? "button-sm" : ""}" data-action="${action}" ${id === undefined ? "" : `data-id="${id}"`}>${symbol ? icon(symbol) : ""}${text}</button>`;
}

function pill(label, tone) {
  return `<span class="pill pill-${tone}">${label}</span>`;
}

function stamp(date) {
  if (!date) return '<span class="event-missing" aria-label="События пока нет">—</span>';
  return `<time datetime="${esc(date)}" class="event-time">${formatter.format(new Date(date))}</time>`;
}

function header(title, description, action = "") {
  return `<div class="page-head"><div><h1 id="main-heading" tabindex="-1">${title}</h1>${description ? `<p>${description}</p>` : ""}</div>${action}</div>`;
}

function empty(title, text, action = "") {
  return `<div class="empty empty-action">${tile("list")}<strong>${title}</strong><p>${text}</p>${action}</div>`;
}

function showToast(text) {
  notice.textContent = text;
  notice.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { notice.hidden = true; }, 5000);
}

function menuOpen(open) {
  menu.setAttribute("aria-expanded", String(open));
  menu.setAttribute("aria-label", open ? "Закрыть меню" : "Открыть меню");
  sidebar.classList.toggle("mobile-open", open);
  backdrop.hidden = !open;
}

async function request(path, data) {
  const init = data === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  };
  let result;
  let response;
  try {
    response = await fetch(path, init);
    result = await response.json();
  } catch {
    throw new Error("Связь с порталом прервалась. Проверьте подключение.");
  }
  if (!response.ok) throw Object.assign(new Error(result.error ?? "Не удалось выполнить действие."), { status: response.status });
  return result;
}

function accountPage() {
  return ui.account?.role === "admin" ? adminPages : learnerPages;
}

function route() {
  menuOpen(false);
  if (!ui.account) return;
  const pages = accountPage();
  const hash = location.hash.slice(1);
  ui.page = Object.hasOwn(pages, hash) ? hash : Object.keys(pages)[0];
  if (ui.page === "lessons") ui.lesson = null;
  render();
}

function go(page) {
  if (location.hash === `#${page}`) route();
  else location.hash = page;
}

function loginView() {
  ui.data = null;
  ui.campaign = null;
  ui.lesson = null;
  shell.hidden = true;
  main.replaceChildren();
  document.querySelector("#navigation").replaceChildren();
  auth.hidden = false;
  document.title = "Вход · Практика ИБ";
  document.getElementById("account-name").textContent = "";
  document.getElementById("account-email").textContent = "";
  notice.hidden = true;
  auth.innerHTML = `<section class="auth-card panel">
    <div class="auth-visual">
      <div class="radar" aria-hidden="true"></div>
      <span class="brand-symbol">${icon("shield")}</span>
      <h2>Практика ИБ</h2>
      <p>Корпоративный портал обучения информационной безопасности.</p>
    </div>
    <div class="auth-body">
      <h1 id="main-heading" tabindex="-1">Вход в портал</h1>
      <p>Используйте свой рабочий адрес и пароль учебного портала.</p>
      <form id="login" class="auth-fields">
        <div><label class="field-label" for="email">Рабочая почта</label><input class="control" id="email" name="email" type="email" autocomplete="username" maxlength="254" required></div>
        <div><label class="field-label" for="password">Пароль портала</label><input class="control" id="password" name="password" type="password" autocomplete="current-password" maxlength="128" required></div>
        <button class="button button-primary" type="submit">Войти</button>
      </form>
      <div class="auth-error notice notice-error" id="login-error" role="alert" hidden></div>
    </div></section>`;
}

function selectedCampaign() {
  return ui.data.campaigns.find((entry) => entry.id === ui.campaign) ?? ui.data.campaigns[0];
}

function scenario(id) {
  return ui.data.scenarios.find((entry) => entry.id === id);
}

function person(id) {
  return ui.data.people.find((entry) => entry.id === id);
}

function enrollAction() {
  return button("Новая кампания", "new-campaign", { symbol: "plus" });
}

function personAction() {
  return button("Добавить сотрудника", "new-person", { symbol: "plus" });
}

function assignmentStatus(row) {
  if (row.completed_at) return pill("Завершено", "live");
  if (row.started_at) return pill("В работе", "review");
  return pill("Назначено", "neutral");
}

function metrics(campaign) {
  const rows = campaign?.assignments ?? [];
  const totals = [
    ["Назначено", rows.length, "users", "mint"],
    ["Начали", rows.filter((row) => row.started_at).length, "activity", "blue"],
    ["Завершили", rows.filter((row) => row.completed_at).length, "check", "purple"],
    ["Письма приняты Zimbra", rows.filter((row) => row.mail_status === "accepted").length, "inbox", "amber"],
  ];
  return `<section class="metrics" aria-label="Показатели кампании">${totals.map(([label, count, image, tone]) => `
    <article class="metric panel"><div class="metric-label">${label}</div><div class="metric-value">${count}</div>${tile(image, tone)}</article>`).join("")}</section>`;
}

function reportTable(campaign) {
  const search = ui.search.trim().toLocaleLowerCase("ru-RU");
  const rows = campaign.assignments.filter((row) => {
    const employee = person(row.account_id);
    return `${employee.name} ${employee.email} ${employee.department}`.toLocaleLowerCase("ru-RU").includes(search);
  });
  if (!rows.length) return empty("Сотрудники не найдены", "Попробуйте изменить поисковый запрос.");
  return `<div class="table-wrap" role="region" aria-label="Результаты кампании" tabindex="0">
    <table class="data-table"><thead><tr><th scope="col">Сотрудник</th><th scope="col">Упражнение</th><th scope="col">Завершение · мск</th><th scope="col">Приглашение</th><th scope="col">Действие</th></tr></thead><tbody>
    ${rows.map((row) => {
      const employee = person(row.account_id);
      const [status, tone] = mailLabels[row.mail_status];
      const maySend = ui.data.mail.configured && ["pending", "rejected"].includes(row.mail_status);
      return `<tr><td class="table-person"><strong>${esc(employee.name)}</strong><small class="secondary">${esc(employee.department)}</small></td>
        <td>${assignmentStatus(row)}${row.completed_at ? `<div class="secondary">${row.correct ? "Верный ответ" : "Открыт разбор"}</div>` : ""}</td>
        <td>${stamp(row.completed_at)}</td>
        <td class="report-status" ${row.mail_id ? `title="Message-ID ${esc(row.mail_id)}"` : ""}>${pill(status, tone)}${row.accepted_at ? `<div class="secondary">${stamp(row.accepted_at)}</div>` : ""}</td>
        <td>${maySend ? button("Отправить", "invite", { kind: "secondary", id: row.id, compact: true }) : '<span class="event-missing">—</span>'}</td></tr>`;
    }).join("")}</tbody></table></div>`;
}

function overviewView() {
  const campaign = selectedCampaign();
  const next = ui.data.people.length ? enrollAction() : personAction();
  const name = campaign ? esc(campaign.name) : ui.data.people.length ? "Назначьте первую кампанию" : "Добавьте первого сотрудника";
  return `${header("Обзор кампании", "", next)}
    <section class="hero"><div class="radar" aria-hidden="true"></div><div class="hero-content">
      <p class="hero-label">${campaign ? "Выбранная кампания" : "Начало работы"}</p>
      <h2>${name}</h2>
      <div class="hero-meta">${campaign
        ? `<span>${icon("calendar")}${stamp(campaign.created_at)}</span><span>${icon("layers")}${esc(scenario(campaign.assignments[0].scenario_id).name)}</span>`
        : "Выберите сотрудника и назначьте ему упражнение из каталога."}</div>
    </div></section>
    ${metrics(campaign)}
    <section class="panel report-panel">
      <div class="panel-head"><h2>Именной отчёт</h2>${campaign ? button("Обновить", "refresh", { kind:"secondary", symbol:"refresh", compact:true }) : ""}</div>
      ${campaign ? `<div class="filters">
        <div class="search-field">${icon("search")}<input class="control" id="report-search" type="search" placeholder="Найти сотрудника" aria-label="Найти сотрудника" value="${esc(ui.search)}"></div>
        <div class="filter-control"><label class="secondary" for="report-campaign">Кампания</label>
          <select class="control" id="report-campaign">${ui.data.campaigns.map((item) => `<option value="${item.id}" ${item.id === campaign.id ? "selected" : ""}>${esc(item.name)}</option>`).join("")}</select></div>
      </div><div id="report-results">${reportTable(campaign)}</div>` : empty("Кампаний пока нет", "Результаты появятся после назначения упражнений.")}
    </section>`;
}

function campaignsView() {
  const rows = ui.data.campaigns.map((entry) => `<tr><td><strong>${esc(entry.name)}</strong></td>
    <td>${stamp(entry.created_at)}</td><td>${entry.assignments.length}</td>
    <td>${entry.assignments.filter((row) => row.completed_at).length}</td>
    <td>${button("Открыть отчёт", "report", { kind: "secondary", id: entry.id, compact: true })}</td></tr>`).join("");
  return `${header("Кампании", "Назначения и результаты обучения.", enrollAction())}<section class="panel campaigns-table">
    ${rows ? `<div class="table-wrap" role="region" aria-label="Кампании" tabindex="0"><table class="data-table">
      <thead><tr><th>Кампания</th><th>Создана · мск</th><th>Участники</th><th>Завершили</th><th>Отчёт</th></tr></thead><tbody>${rows}</tbody></table></div>`
      : empty("Кампаний пока нет", "Назначьте упражнение сотрудникам, чтобы начать обучение.")}</section>`;
}

function participantsView() {
  const rows = ui.data.people.map((employee) => `<tr><td><strong>${esc(employee.name)}</strong></td>
    <td>${esc(employee.department)}</td><td>${esc(employee.email)}</td></tr>`).join("");
  return `${header("Сотрудники", "Управление доступом сотрудников к порталу.", personAction())}<section class="panel">
    ${rows ? `<div class="table-wrap" role="region" aria-label="Сотрудники" tabindex="0"><table class="data-table">
      <thead><tr><th>ФИО</th><th>Подразделение</th><th>Рабочая почта</th></tr></thead><tbody>${rows}</tbody></table></div>`
      : empty("Список пока пуст", "Добавьте сотрудника, чтобы выдать ему доступ к порталу.")}</section>`;
}

function scenariosView() {
  return `${header("Сценарии", "Упражнения для разбора сообщений внутри портала.")}
    <section class="scenario-grid" aria-label="Каталог сценариев">${ui.data.scenarios.map((item) => {
      const [image, tone] = theme[item.id];
      return `<article class="panel scenario-card tone-${tone}">${tile(image, tone)}
        <div><div class="category">${esc(item.category)}</div><h2>${esc(item.name)}</h2><p>${esc(item.description)}</p></div>
        ${button("Назначить", "new-campaign", { kind: "secondary", id: item.id })}</article>`;
    }).join("")}</section>`;
}

function mailView() {
  const mail = ui.data.mail;
  return `${header("Почта", "Доставка учебных приглашений через Zimbra.")}
    <section class="panel mail-settings">
      <h2>Подключение SMTP</h2>
      <p class="notice">${icon(mail.configured ? "check" : "info")}
        ${mail.configured ? "Параметры заданы. Отправьте приглашение из именного отчёта, чтобы проверить подключение." : "Настройте подключение к Zimbra по инструкции развёртывания."}</p>
      <dl><dt>Отправитель</dt><dd>${esc(mail.sender ?? "Не настроен")}</dd>
      <dt>Домен получателей</dt><dd>${esc(ui.data.domain)}</dd><dt>Адрес портала</dt><dd>${esc(mail.portal)}</dd></dl>
      <p class="secondary">Статус «Принято Zimbra» означает, что сервер принял SMTP-сообщение. Доставку можно сверить в ящике или по Message-ID.</p>
    </section>`;
}

function learnerView() {
  const entries = ui.data.lessons;
  const current = entries.find((entry) => entry.id === ui.lesson);
  if (current) return exerciseView(current);
  return `${header("Мои задания", "Назначенные упражнения по информационной безопасности.")}
    ${entries.length ? `<section class="scenario-grid">
      ${entries.map((entry) => {
        const [symbol, tone] = theme[entry.exercise.id];
        return `<article class="panel lesson-card">
          ${tile(symbol, tone)}<p class="secondary">${esc(entry.campaign)}</p><h2>${esc(entry.exercise.name)}</h2>
          ${assignmentStatus(entry)}<div>${button(entry.completed_at ? "Посмотреть разбор" : entry.started_at ? "Продолжить" : "Начать упражнение", "open-lesson", { id: entry.id })}</div>
        </article>`;
      }).join("")}</section>` : `<section class="panel">${empty("Заданий пока нет", "Когда вам назначат упражнение, оно появится здесь.")}</section>`}`;
}

function exerciseView(entry) {
  const item = entry.exercise;
  const [image, tone] = theme[item.id];
  return `${header(esc(item.name), esc(entry.campaign), button("К заданиям", "back-lessons", { kind: "secondary" }))}
    <article class="panel lesson-content">
      ${tile(image, tone)}<h2>Учебный пример</h2><blockquote>${esc(item.example)}</blockquote>
      ${entry.completed_at ? `<h2>${entry.correct ? "Верный ответ" : "Разбор ответа"}</h2><p>${esc(entry.feedback)}</p>` : `
        <form id="answer-lesson">
          <fieldset class="answers"><legend>${esc(item.question)}</legend>
          ${item.choices.map((choice, index) => `<label class="answer-option"><input type="radio" name="answer" value="${index}" required>${esc(choice)}</label>`).join("")}</fieldset>
          <button class="button button-primary" type="submit">Проверить ответ</button>
          <p class="notice notice-error" id="lesson-error" role="alert" hidden></p>
        </form>`}
    </article>`;
}

function render() {
  if (!ui.account) return loginView();
  const pages = accountPage();
  const [title] = pages[ui.page];
  auth.hidden = true;
  auth.replaceChildren();
  shell.hidden = false;
  document.title = `${title} · Практика ИБ`;
  document.getElementById("topbar-page").textContent = title;
  document.getElementById("account-name").textContent = ui.account.name;
  document.getElementById("account-email").textContent = ui.account.email;
  document.getElementById("navigation").innerHTML = Object.entries(pages).map(([path, [name, symbol]]) => `
    <a class="nav-link" href="#${path}" ${path === ui.page ? 'aria-current="page"' : ""}>${icon(symbol)}${name}</a>`).join("");
  const views = { overview: overviewView, campaigns: campaignsView, participants: participantsView, scenarios: scenariosView, mail: mailView, lessons: learnerView };
  main.innerHTML = ui.data ? views[ui.page]() : '<div class="loading panel" role="status">Загрузка…</div>';
}

async function refresh() {
  try {
    ui.data = await request(ui.account.role === "admin" ? "/api/admin" : "/api/lessons");
    render();
  } catch (error) {
    if (error.status === 401) {
      ui.account = null;
      if (dialog.open) dialog.close();
      loginView();
    }
    throw error;
  }
}

async function enter(user) {
  ui.account = user;
  if (!user) return loginView();
  route();
  try {
    await refresh();
  } catch (error) {
    if (ui.account) main.innerHTML = `<section class="panel">${empty("Данные пока недоступны", esc(error.message), button("Повторить", "refresh", { kind: "secondary" }))}</section>`;
  }
}

function dialogHeading(title, symbol) {
  return `<div class="dialog-head"><div>${tile(symbol)}<h2 id="dialog-title">${title}</h2></div>
    <button type="button" data-action="close" class="icon-button" aria-label="Закрыть">${icon("close")}</button></div>`;
}

function dialogForm(form, title, symbol, content, submitText) {
  dialog.innerHTML = `${dialogHeading(title, symbol)}<form id="${form}">
    <div class="dialog-body"><div class="overlay-fields">${content}</div>
      <div class="notice notice-error dialog-error" id="dialog-error" role="alert" hidden></div></div>
    <div class="dialog-actions">${button("Отмена", "close", { kind:"secondary" })}<button type="submit" class="button button-primary">${submitText}</button></div>
  </form>`;
  if (!dialog.open) dialog.showModal();
}

function field(label, key, maxlength, type = "text") {
  return `<div><label class="field-label" for="${key}">${label}</label><input class="control" name="${key}" id="${key}" type="${type}" maxlength="${maxlength}" required></div>`;
}

function participantDialog() {
  dialogForm("new-participant", "Новый сотрудник", "users",
    field("ФИО", "name", 90) + field("Подразделение", "department", 70) + field(`Рабочий адрес @${esc(ui.data.domain)}`, "email", 254, "email"),
    "Создать учётную запись");
}

function campaignDialog(selected) {
  if (!ui.data.people.length) return participantDialog();
  dialogForm("new-campaign", "Новая кампания", "campaign",
    `${field("Название кампании", "name", 90)}
    <div><label class="field-label" for="scenario">Упражнение</label><select class="control" name="scenario" id="scenario">${
      ui.data.scenarios.map((item) => `<option value="${item.id}" ${item.id === selected ? "selected" : ""}>${esc(item.name)}</option>`).join("")
    }</select></div>
    <div><p class="field-label">Сотрудники</p><div class="enrollment-grid">
      ${ui.data.people.map((employee) => `<label><input type="checkbox" name="participants" value="${employee.id}"><span>${esc(employee.name)}<small>${esc(employee.department)} · ${esc(employee.email)}</small></span></label>`).join("")}
    </div></div>`, "Назначить упражнение");
}

function inviteDialog(id) {
  const entry = selectedCampaign().assignments.find((row) => row.id === id);
  dialogForm("send-invitation", "Учебное приглашение", "inbox",
    `<p>Отправить служебное письмо на <strong>${esc(person(entry.account_id).email)}</strong>?</p>
    <p class="secondary">Отправитель ${esc(ui.data.mail.sender)}. В письме будет адрес учебного портала.</p>
    <input type="hidden" name="assignment_id" value="${id}">`, "Отправить через Zimbra");
}

function showCredentials(result) {
  dialog.innerHTML = `${dialogHeading("Учётная запись создана", "check")}<div class="dialog-body">
    <p>Передайте данные для входа сотруднику по внутреннему каналу. Пароль показывается один раз.</p>
    <div class="overlay-fields">
      <div><label class="field-label" for="new-email">Рабочий адрес</label><input class="control" id="new-email" value="${esc(result.email)}" readonly></div>
      <div><label class="field-label" for="new-password">Пароль портала</label><input class="control print-once" id="new-password" value="${esc(result.password)}" readonly></div>
    </div></div><div class="dialog-actions">${button("Готово", "close")}</div>`;
}

function showFieldError(element, message) {
  element.hidden = false;
  element.textContent = message;
}

auth.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = event.submitter;
  const form = event.target;
  const values = Object.fromEntries(new FormData(form));
  const errorBox = auth.querySelector("#login-error");
  submit.disabled = true;
  errorBox.hidden = true;
  try {
    const response = await request("/api/login", values);
    await enter(response.user);
  } catch (error) {
    form.elements.password.value = "";
    showFieldError(errorBox, error.message);
    form.elements.password.focus();
  } finally {
    submit.disabled = false;
  }
});

dialog.addEventListener("click", (event) => {
  if (event.target.closest("[data-action=close]") && !ui.busy) dialog.close();
});
dialog.addEventListener("cancel", (event) => {
  if (ui.busy) event.preventDefault();
});
dialog.addEventListener("close", () => {
  if (!dialog.open) dialog.replaceChildren();
});

dialog.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (ui.busy) return;
  ui.busy = true;
  const submit = event.submitter;
  const data = new FormData(event.target);
  const errorBox = dialog.querySelector("#dialog-error");
  errorBox.hidden = true;
  submit.disabled = true;
  try {
    switch (event.target.id) {
      case "new-participant": {
        const created = await request("/api/admin/participants", Object.fromEntries(data));
        showCredentials(created);
        go("participants");
        break;
      }
      case "new-campaign": {
        const created = await request("/api/admin/campaigns", {
          name: data.get("name"), scenario: data.get("scenario"), participants: data.getAll("participants").map(Number),
        });
        ui.campaign = created.id;
        ui.search = "";
        dialog.close();
        go("overview");
        break;
      }
      case "send-invitation": {
        const { status } = await request("/api/admin/invitation", { assignment_id: Number(data.get("assignment_id")) });
        dialog.close();
        showToast(mailLabels[status][0]);
        break;
      }
    }
    await refresh().catch((error) => showToast(error.message));
  } catch (error) {
    showFieldError(errorBox, error.message);
  } finally {
    ui.busy = false;
    submit.disabled = false;
  }
});

main.addEventListener("click", async (event) => {
  const controller = event.target.closest("[data-action]");
  if (!controller || ui.busy) return;
  const { action, id } = controller.dataset;
  try {
    switch (action) {
      case "new-person": participantDialog(); break;
      case "new-campaign": campaignDialog(id); break;
      case "invite": inviteDialog(Number(id)); break;
      case "report":
        ui.campaign = Number(id);
        ui.search = "";
        go("overview");
        break;
      case "refresh":
        await refresh();
        showToast("Данные обновлены");
        break;
      case "back-lessons":
        ui.lesson = null;
        render();
        break;
      case "open-lesson": {
        const lesson = ui.data.lessons.find((entry) => entry.id === Number(id));
        if (!lesson.started_at) {
          ui.busy = true;
          controller.disabled = true;
          await request("/api/lesson/start", { assignment_id: lesson.id });
        }
        ui.lesson = lesson.id;
        await refresh();
        break;
      }
    }
  } catch (error) {
    showToast(error.message);
  } finally {
    ui.busy = false;
    controller.disabled = false;
  }
});

main.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (event.target.id !== "answer-lesson" || ui.busy) return;
  ui.busy = true;
  const form = event.target;
  const submit = event.submitter;
  submit.disabled = true;
  try {
    const answer = new FormData(form).get("answer");
    if (answer === null) return;
    await request("/api/lesson/answer", { assignment_id: ui.lesson, answer: Number(answer) });
    await refresh().catch((error) => showToast(error.message));
  } catch (error) {
    showFieldError(form.querySelector("#lesson-error"), error.message);
  } finally {
    ui.busy = false;
    submit.disabled = false;
  }
});

main.addEventListener("input", (event) => {
  if (event.target.id !== "report-search") return;
  ui.search = event.target.value;
  main.querySelector("#report-results").innerHTML = reportTable(selectedCampaign());
});
main.addEventListener("change", (event) => {
  if (event.target.id !== "report-campaign") return;
  ui.campaign = Number(event.target.value);
  render();
  main.querySelector("#report-campaign").focus();
});

document.getElementById("logout").addEventListener("click", async () => {
  if (ui.busy) return;
  try {
    await request("/api/logout", {});
    await enter(null);
  } catch (error) {
    showToast(error.message);
  }
});
document.querySelector(".skip-link").addEventListener("click", (event) => {
  event.preventDefault();
  document.getElementById("main-heading")?.focus();
});
menu.addEventListener("click", () => menuOpen(menu.getAttribute("aria-expanded") !== "true"));
backdrop.addEventListener("click", () => { menuOpen(false); menu.focus(); });
document.getElementById("navigation").addEventListener("click", () => menuOpen(false));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && menu.getAttribute("aria-expanded") === "true") {
    menuOpen(false);
    menu.focus();
  }
});
window.addEventListener("hashchange", route);

void request("/api/session").then(({ user }) => enter(user)).catch((error) => {
  auth.textContent = error.message;
});
