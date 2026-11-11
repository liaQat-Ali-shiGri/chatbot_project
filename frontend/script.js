let currentSessionId = null;
let sessions = [];
// The reply that still needs feedback ({message_id, session_id}), from any chat (FR12, FR13).
let pendingFeedback = null;

const SESSION_ENDED_TEXT = "This session has ended. Start a new chat to continue.";

function generateSessionId() {
    return Date.now().toString() + Math.random().toString(36).slice(2, 8);
}

// All API calls go through here; an expired login sends the user back to the sign-in page.
async function api(url, body = null) {
    const options = { credentials: "include" };
    if (body !== null) {
        options.method = "POST";
        options.headers = { "Content-Type": "application/json" };
        options.body = JSON.stringify(body);
    }
    const response = await fetch(url, options);
    if (response.status === 401) {
        window.location.href = "/";
        throw new Error("Not logged in");
    }
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : {};
    if (!response.ok) {
        throw new Error(data.error || `Server returned HTTP ${response.status}`);
    }
    return data;
}

// Check authentication and load user data
async function checkAuthAndLoad() {
    try {
        const user = await api("/api/user");
        setChatLocked(false);
        document.getElementById("sidebar-user-name").innerText = user.name;
        document.getElementById("sidebar-user-email").innerText = user.email;

        document.getElementById("chat-messages").innerHTML = "";
        currentSessionId = generateSessionId();
        addMessage("bot", `Welcome ${user.name}! I'm your LLaMA 3 chatbot. Ask me anything.`);
        await loadChatHistory();
        // A reply left unrated (e.g. before a page reload) is opened so its feedback can be given.
        if (pendingFeedback) {
            await switchToSession(pendingFeedback.session_id);
        }
    } catch (error) {
        console.error("Auth error:", error);
        window.location.href = "/";
    }
}

// Theme toggle: dark mode is a class on <body>, remembered in this browser.
const themeToggle = document.getElementById("theme-toggle");

function applyTheme(dark) {
    document.body.classList.toggle("dark-theme", dark);
    themeToggle.innerHTML = `<i class="fas ${dark ? "fa-sun" : "fa-moon"}"></i>`;
}

applyTheme(localStorage.getItem("theme") === "dark");
themeToggle.addEventListener("click", () => {
    const dark = !document.body.classList.contains("dark-theme");
    localStorage.setItem("theme", dark ? "dark" : "light");
    applyTheme(dark);
});

// Logout
document.getElementById("sidebar-logout").onclick = async () => {
    await api("/api/logout", {});
    window.location.href = "/";
};

// Analytics link
document.getElementById("analytics-link").onclick = () => {
    window.location.href = `/analytics?session_id=${encodeURIComponent(currentSessionId)}`;
};

// Load chat history
let titleRefreshTimer = null;

async function loadChatHistory() {
    try {
        const data = await api("/api/history/sessions");
        sessions = data.sessions;
        pendingFeedback = data.pending_feedback;
        updateHistoryList();
        // Titles are written in the background; refresh the list until they have all arrived.
        clearTimeout(titleRefreshTimer);
        if (data.titles_pending > 0) {
            titleRefreshTimer = setTimeout(loadChatHistory, 4000);
        }
    } catch (error) {
        console.error("Could not load chat history:", error);
    }
}

// Update sidebar history list
function updateHistoryList() {
    const historyList = document.getElementById("history-list");
    historyList.innerHTML = '<div class="history-item" data-session="current"><i class="fas fa-comment"></i> Current Chat</div>';

    // The server lists the most recently active chats first.
    for (const session of sessions) {
        const div = document.createElement("div");
        div.className = "history-item";
        div.innerHTML = `<i class="fas ${session.ended ? "fa-flag-checkered" : "fa-message"}"></i>`;
        const label = document.createElement("span");
        label.className = "history-title";
        label.textContent = session.title;
        div.appendChild(label);
        div.title = session.ended ? `${session.title} (ended)` : session.title;
        div.dataset.session = session.session_id;
        div.onclick = () => switchToSession(session.session_id);
        historyList.appendChild(div);
    }

    const openChat = [...historyList.children].find(item => item.dataset.session === currentSessionId)
        || historyList.firstElementChild;
    openChat.classList.add("active");
}

// Switch to a different chat session
async function switchToSession(sessionId) {
    let data;
    try {
        data = await api(`/api/history/${encodeURIComponent(sessionId)}`);
    } catch (error) {
        alert("Could not open this chat: " + error.message);
        return;
    }
    currentSessionId = sessionId;

    document.querySelectorAll(".history-item").forEach(item => {
        item.classList.toggle("active", item.dataset.session === sessionId);
    });

    const chatBox = document.getElementById("chat-messages");
    chatBox.innerHTML = "";

    let lastReply = null;
    for (const msg of data.messages) {
        const element = addMessage(msg.role, msg.content);
        if (msg.role !== "bot") continue;
        lastReply = { element, msg };
        // Rated replies show the feedback that was given on them.
        const badges = msg.feedback && buildFeedbackBadges(msg.feedback);
        if (badges) element.appendChild(badges);
    }
    setSessionEnded(Boolean(data.ended));

    // The reply that still needs feedback gets its panel back; any other chat stays locked until it is rated.
    if (data.ended) return;
    if (lastReply?.msg.message_id && !lastReply.msg.feedback) {
        requestFeedback(lastReply.element, lastReply.msg.message_id);
    } else if (pendingFeedback && pendingFeedback.session_id !== sessionId) {
        setChatLocked(true, "Rate your last reply in your other chat first");
    }
}

// Shows where feedback is still owed: the panel in this chat, or the chat that holds it.
function showPendingFeedback(message) {
    const panel = document.querySelector("#chat-messages .feedback-panel-wrap");
    if (panel) {
        panel.querySelector(".feedback-hint").textContent = message;
        panel.scrollIntoView({ behavior: "smooth", block: "center" });
    } else if (pendingFeedback) {
        switchToSession(pendingFeedback.session_id);
    }
}

// New chat
function newChat() {
    if (pendingFeedback) {
        showPendingFeedback("Please rate this reply before starting a new chat");
        return;
    }
    currentSessionId = generateSessionId();
    setSessionEnded(false);

    document.getElementById("chat-messages").innerHTML = "";
    addMessage("bot", "✨ New chat started! How can I help you?");

    document.querySelectorAll(".history-item").forEach(item => {
        item.classList.toggle("active", item.dataset.session === "current");
    });
}

// Send message
async function sendMessage() {
    const input = document.getElementById("message-input");
    const message = input.value.trim();
    if (!message || input.disabled) return;

    // The reply belongs to the chat it was asked in, even if the user switches chats meanwhile.
    const sessionId = currentSessionId;
    addMessage("user", message);
    input.value = "";
    setChatLocked(true, "Waiting for the reply...");

    const loading = addMessage("bot", "", true);

    try {
        const data = await api("/api/chat", { message: message, session_id: sessionId });
        loading.remove();
        pendingFeedback = { message_id: data.message_id, session_id: sessionId };
        if (currentSessionId === sessionId) {
            requestFeedback(addMessage("bot", data.response), data.message_id);
        }
        loadChatHistory();
    } catch (error) {
        loading.remove();
        addMessage("bot", "❌ Error: " + error.message);
        setChatLocked(false);
    }
}

// Bot replies are written in Markdown (bold, lists, tables). The HTML is sanitized
// so a reply can never inject scripts; without the libraries, plain text is shown.
if (window.DOMPurify) {
    DOMPurify.addHook("afterSanitizeAttributes", node => {
        if (node.tagName === "A") {
            node.setAttribute("target", "_blank");
            node.setAttribute("rel", "noopener noreferrer");
        }
    });
}

function renderMarkdown(text) {
    if (!window.marked || !window.DOMPurify) return null;
    return DOMPurify.sanitize(marked.parse(String(text || ""), { gfm: true, breaks: true }));
}

function addMessage(sender, text, isTyping = false) {
    const container = document.getElementById("chat-messages");
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${sender}`;

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    
    const markdown = sender === "bot" && !isTyping ? renderMarkdown(text) : null;
    if (isTyping) {
        bubble.classList.add("typing-indicator");
        bubble.innerHTML = `<span></span><span></span><span></span>`;
    } else if (markdown !== null) {
        bubble.classList.add("markdown");
        bubble.innerHTML = markdown;
    } else {
        bubble.innerText = String(text || "").replace(/<br\s*\/?>/gi, "\n");
    }
    
    msgDiv.appendChild(bubble);
    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
    return msgDiv;
}

// Mandatory feedback (FR12): exactly the options the project specification defines.
// Rating is shown as four stars; correctness and length as chips with an icon.
const FEEDBACK_ICONS = {
    star: '<path d="M12 2.6l2.85 5.95 6.55.85-4.8 4.55 1.2 6.5L12 17.3l-5.8 3.15 1.2-6.5-4.8-4.55 6.55-.85z"/>',
    correct: '<path d="M5 12.5l4.3 4.3L19 7.2"/>',
    partial: '<circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor"/>',
    incorrect: '<path d="M7 7l10 10M17 7L7 17"/>',
    short: '<path d="M5 12h9"/>',
    to_the_point: '<path d="M5 9h14M5 15h9"/>',
    lengthy: '<path d="M5 6h14M5 12h14M5 18h14"/>'
};
const FEEDBACK_FIELDS = [
    { name: "rating", label: "Rating" },
    { name: "correctness", label: "Correctness", tone: true,
      options: [["correct", "Correct", "good"], ["partial", "Partial", "warn"], ["incorrect", "Incorrect", "bad"]] },
    { name: "length_type", label: "Length",
      options: [["short", "Short"], ["to_the_point", "To the Point"], ["lengthy", "Lengthy"]] }
];

function feedbackValue(panel, name) {
    return panel.querySelector(`.feedback-group[data-field="${name}"] [aria-checked="true"]`)?.dataset.value || "";
}

function buildFeedbackPanel(msgId) {
    const panel = document.createElement("div");
    panel.className = "feedback-panel-wrap";

    const stars = [1, 2, 3, 4].map(n =>
        `<button type="button" class="feedback-star" role="radio" aria-checked="false" aria-label="${n} out of 4" data-value="${n}">` +
        `<svg viewBox="0 0 24 24" aria-hidden="true">${FEEDBACK_ICONS.star}</svg></button>`).join("");
    const chips = field => field.options.map(([value, text, tone]) =>
        `<button type="button" class="feedback-chip ${tone || "plain"}" role="radio" aria-checked="false" data-value="${value}">` +
        `<svg viewBox="0 0 24 24" aria-hidden="true">${FEEDBACK_ICONS[value]}</svg>${text}</button>`).join("");

    // One line under the reply: stars | correctness chips | length chips | Submit.
    // A missing-answer note appears just below it, so the line itself never wraps.
    panel.innerHTML = `
        <div class="feedback-panel" role="group" aria-label="Rate this reply">
            <div class="feedback-group" data-field="rating" title="Rating (1-4)">
                <div class="feedback-stars" role="radiogroup" aria-label="Rating, 1 to 4">${stars}</div>
                <span class="feedback-star-value">–/4</span>
            </div>
            ${FEEDBACK_FIELDS.slice(1).map(field => `
            <span class="feedback-divider" aria-hidden="true"></span>
            <div class="feedback-group" data-field="${field.name}" title="${field.label}">
                <div class="feedback-chips" role="radiogroup" aria-label="${field.label}">${chips(field)}</div>
            </div>`).join("")}
            <button type="button" class="feedback-submit-btn">Submit</button>
        </div>
        <div class="feedback-hint" role="alert"></div>`;

    const hint = panel.querySelector(".feedback-hint");
    const paintStars = count => {
        panel.querySelectorAll(".feedback-star").forEach(star => star.classList.toggle("lit", Number(star.dataset.value) <= count));
        panel.querySelector(".feedback-star-value").textContent = count ? `${count}/4` : "–/4";
    };
    const showMissing = () => {
        const missing = FEEDBACK_FIELDS.filter(field => !feedbackValue(panel, field.name));
        panel.querySelectorAll(".feedback-group").forEach(group => {
            group.classList.toggle("feedback-missing", missing.some(field => field.name === group.dataset.field));
        });
        hint.textContent = missing.length ? "Please choose " + missing.map(field => field.label).join(", ") : "";
        return missing;
    };

    panel.querySelectorAll(".feedback-star, .feedback-chip").forEach(option => {
        option.onclick = () => {
            const group = option.closest(".feedback-group");
            group.querySelectorAll("[data-value]").forEach(item => item.setAttribute("aria-checked", String(item === option)));
            group.classList.remove("feedback-missing");
            if (group.dataset.field === "rating") paintStars(Number(option.dataset.value));
            if (hint.textContent) showMissing();
        };
    });
    // Hovering the stars previews the rating; leaving shows the chosen one again.
    const starGroup = panel.querySelector(".feedback-stars");
    starGroup.addEventListener("pointerover", event => {
        const star = event.target.closest(".feedback-star");
        if (star) paintStars(Number(star.dataset.value));
    });
    starGroup.addEventListener("pointerleave", () => paintStars(Number(feedbackValue(panel, "rating") || 0)));

    // All three answers are required: point out the ones still missing.
    panel.querySelector(".feedback-submit-btn").onclick = () => {
        const missing = showMissing();
        if (missing.length) {
            panel.querySelector(`.feedback-group[data-field="${missing[0].name}"] [data-value]`).focus();
            return;
        }
        submitFeedback(msgId, panel);
    };
    return panel;
}

// The chat is locked until the latest reply is rated (FR13); the panel sits under that reply.
function requestFeedback(reply, msgId) {
    reply.classList.add("has-feedback");
    reply.appendChild(buildFeedbackPanel(msgId));
    setChatLocked(true);

    const container = document.getElementById("chat-messages");
    container.scrollTop = container.scrollHeight;
}

// A rated reply keeps small badges that show the feedback given on it.
// Feedback stored in older formats is skipped part by part rather than shown wrongly.
function buildFeedbackBadges(feedback, justSaved = false) {
    const parts = [];
    const stars = Number(feedback.rating);
    if (stars >= 1 && stars <= 4) {
        parts.push(`<span class="feedback-badge" title="Rating"><span class="feedback-badge-stars">${"★".repeat(stars)}</span>${stars}/4</span>`);
    }
    const correct = FEEDBACK_FIELDS[1].options.find(([key]) => key === feedback.correctness);
    if (correct) {
        parts.push(`<span class="feedback-badge ${correct[2]}" title="Correctness">${correct[1]}</span>`);
    }
    const length = FEEDBACK_FIELDS[2].options.find(([key]) => key === feedback.length_type);
    if (length) {
        parts.push(`<span class="feedback-badge" title="Length">${length[1]}</span>`);
    }
    if (!parts.length) return null;
    if (justSaved) {
        parts.push('<span class="feedback-badge saved"><i class="fas fa-check"></i> Feedback saved</span>');
    }
    const badges = document.createElement("div");
    badges.className = "feedback-badges";
    badges.innerHTML = parts.join("");
    return badges;
}

// Called once all three answers are chosen; the keys match the API and the stored feedback.
async function submitFeedback(msgId, panel) {
    const feedback = Object.fromEntries(FEEDBACK_FIELDS.map(field => [field.name, feedbackValue(panel, field.name)]));
    try {
        await api("/api/feedback", { message_id: msgId, ...feedback });

        panel.replaceWith(buildFeedbackBadges(feedback, true));
        pendingFeedback = null;
        setChatLocked(false);
        document.getElementById("message-input").focus();
    } catch (error) {
        alert("Error: " + error.message);
    }
}

function setChatLocked(locked, reason = "Submit feedback to continue...") {
    document.getElementById("message-input").disabled = locked;
    document.getElementById("send-btn").disabled = locked;
    document.getElementById("message-input").placeholder = locked
        ? reason
        : "Type your message...";
}

function setSessionEnded(ended) {
    document.getElementById("end-session-btn").disabled = ended;
    setChatLocked(ended, SESSION_ENDED_TEXT);
}

// End the session and store its final analytics summary (FR22)
async function endSession() {
    if (!confirm("End this session? Its final analytics summary will be saved and no more messages can be sent in it.")) return;

    try {
        const data = await api("/api/session/end", { session_id: currentSessionId });

        setSessionEnded(true);
        addSessionSummary(data.summary);
        loadChatHistory();
    } catch (error) {
        alert("Error: " + error.message);
    }
}

function addSessionSummary(summary) {
    const kpis = summary.kpis;
    const show = (value, suffix = "") => value === null || value === undefined ? "—" : `${value}${suffix}`;
    const card = document.createElement("div");
    card.className = "session-summary";
    card.innerHTML = `
        <h4><i class="fas fa-flag-checkered"></i> Session ended — final summary saved</h4>
        <div class="session-summary-stats">
            <span><strong>${kpis.replies}</strong> replies</span>
            <span><strong>${show(kpis.accuracy, "%")}</strong> accuracy</span>
            <span><strong>${show(kpis.avg_rating)}</strong> avg rating</span>
            <span><strong>${show(kpis.avg_response_time, " s")}</strong> avg response time</span>
        </div>
        <a href="/analytics?session_id=${encodeURIComponent(summary.session_id)}">
            <i class="fas fa-chart-line"></i> View full session analytics
        </a>
    `;
    const container = document.getElementById("chat-messages");
    container.appendChild(card);
    container.scrollTop = container.scrollHeight;
}

// Event listeners
document.getElementById("send-btn").onclick = sendMessage;
document.getElementById("new-chat-btn").onclick = newChat;
document.getElementById("end-session-btn").onclick = endSession;
document.getElementById("message-input").addEventListener("keypress", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Start the app
checkAuthAndLoad();