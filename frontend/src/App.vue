<template>
  <div class="app-container">
    <div class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-header">
        <span v-if="!sidebarCollapsed" class="sidebar-title">AI Chat</span>
        <el-button text class="sidebar-toggle-btn" @click="sidebarCollapsed = !sidebarCollapsed">
          <el-icon :size="18">
            <Expand v-if="sidebarCollapsed" />
            <Fold v-else />
          </el-icon>
        </el-button>
      </div>
      <div class="sidebar-new-chat-wrap">
        <el-button type="primary" class="new-chat-btn" style="width: 100%" @click="handleNewChat">
          <el-icon><Plus /></el-icon>
          <span v-if="!sidebarCollapsed">新对话</span>
        </el-button>
      </div>
      <div class="session-list">
        <div
          v-for="s in sessionList"
          :key="s.session_id"
          :class="['session-item', { active: s.session_id === sessionId }]"
          @click="switchSession(s.session_id)"
        >
          <el-tooltip :content="s.title" placement="right" :show-after="400">
            <div class="session-title">{{ s.title }}</div>
          </el-tooltip>
          <el-popconfirm title="确定删除该对话？" confirm-button-text="确定" cancel-button-text="取消" @confirm="handleDeleteSession(s.session_id)">
            <template #reference>
              <el-button text size="small" class="delete-btn" @click.stop>
                <el-icon><Delete /></el-icon>
              </el-button>
            </template>
          </el-popconfirm>
        </div>
      </div>
    </div>

    <div class="chat-layout">
      <header class="chat-header">
        <div class="header-left">
          <span class="header-title">AI Chat</span>
          <el-select v-model="selectedModel" class="model-select" size="small" placeholder="模型">
            <el-option v-for="opt in modelOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
          <el-select
            v-model="selectedSkills"
            multiple
            collapse-tags
            class="skill-select"
            size="small"
            placeholder="选择技能"
            :max-collapse-tags="1"
            @change="handleSkillsChange"
          >
            <el-option
              v-for="opt in SKILL_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </div>
        <div class="header-right">
          <el-button text :disabled="loading" @click="handleNewChat">
            <el-icon><Plus /></el-icon>
            新对话
          </el-button>
        </div>
      </header>
      <main class="chat-content">
        <div ref="messageListRef" class="message-list">
          <div v-if="messages.length === 0" class="empty-state">
            <div class="empty-icon-wrap">
              <el-icon class="empty-icon" :size="36"><ChatDotRound /></el-icon>
            </div>
            <p class="empty-title">你好，有什么可以帮你？</p>
            <p class="empty-hint">输入消息开始对话，支持多轮上下文</p>
          </div>
          <div
            v-for="msg in messages"
            :key="msg.id"
            :class="['message-row', msg.role === 'user' ? 'message-user' : 'message-assistant']"
          >
            <el-avatar :size="32" :class="['msg-avatar', msg.role === 'user' ? 'avatar-user' : 'avatar-assistant']">
              <el-icon><User v-if="msg.role === 'user'" /><ChatDotRound v-else /></el-icon>
            </el-avatar>
            <div class="message-bubble" :class="`bubble-${msg.role}`">
              <div v-html="renderMarkdown(msg.content)"></div>
              <div
                v-if="msg.role === 'assistant' && msg.id === streamingMsgId && loading && !msg.done"
                class="cursor-blink"
              >
                |
              </div>
            </div>
          </div>
        </div>
      </main>
      <footer class="chat-footer">
        <div class="input-area">
          <div class="input-wrapper">
            <el-input
              :key="inputKey"
              v-model="inputText"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 4 }"
              :placeholder="loading ? 'AI 正在回复...' : '输入消息，Enter 发送（Shift+Enter 换行）'"
              :disabled="loading"
              resize="none"
              class="chat-input"
              @keydown="handleInputKeydown"
            />
          </div>
          <el-button v-if="!loading" type="primary" class="send-btn" :disabled="!inputText.trim()" @click="handleSend">
            <el-icon><Promotion /></el-icon>
          </el-button>
          <el-button v-else type="danger" class="stop-btn stop-btn-wide" @click="handleStop">
            <el-icon><VideoPause /></el-icon>
            <span class="stop-label">停止</span>
          </el-button>
        </div>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from "vue";
import { ElMessage } from "element-plus";
import {
  Plus,
  Delete,
  Promotion,
  User,
  Fold,
  Expand,
  ChatDotRound,
  VideoPause,
} from "@element-plus/icons-vue";

const API_BASE = "/api";
const ACTIVE_SESSION_KEY = "ai_chat_active_session_id";

function persistActiveSessionId(id) {
  if (id) sessionStorage.setItem(ACTIVE_SESSION_KEY, id);
}

function readStoredSessionId() {
  return sessionStorage.getItem(ACTIVE_SESSION_KEY) || "";
}

function isValidSessionIdFormat(id) {
  return /^sess_\d+_[a-z0-9]{6}$/.test(id);
}

const inputText = ref("");
const inputKey = ref(0);
const messages = ref([]);
const loading = ref(false);
const messageListRef = ref(null);
const sessionId = ref("");
const sessionList = ref([]);
const selectedModel = ref("qwen3.6-plus");
const sidebarCollapsed = ref(false);
const selectedSkills = ref([]);
const streamingMsgId = ref(null);

const modelOptions = [{ label: "qwen3.6-plus", value: "qwen3.6-plus" }];

/** 与后端 `pw-skill` 插件对应的一组 skill id（settings 里需分别开关 slash 命令） */
const PW_SUITE = "playwright-suite";
const PW_SUITE_MEMBERS = ["pw-browse", "pw-launch", "pw-close", "pw-test"];

const SKILL_OPTIONS = [
  { label: "前端设计", value: "frontend-design" },
  { label: "创建技能", value: "skill-creator" },
  { label: "Playwright 浏览器（自动化）", value: PW_SUITE },
];

function skillsToApi(local) {
  const out = [];
  for (const s of local || []) {
    if (s === PW_SUITE) {
      out.push(...PW_SUITE_MEMBERS);
    } else {
      out.push(s);
    }
  }
  return [...new Set(out)];
}

/** 会话里若存在任一 pw-*，则 UI 显示为勾选了套件一项 */
function skillsFromApi(apiList) {
  const list = apiList || [];
  const hasPw = PW_SUITE_MEMBERS.some((m) => list.includes(m));
  const rest = list.filter((s) => !PW_SUITE_MEMBERS.includes(s));
  if (hasPw) rest.push(PW_SUITE);
  return [...new Set(rest)];
}

let msgSeq = 0;
let abortController = null;
let skillsSyncTimer = null;
/** 避免程序化回填技能时触发 PATCH */
let skipSkillsChangeEmit = false;

function generateId() {
  return "sess_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
}

function nextMsgId() {
  msgSeq += 1;
  return `m_${Date.now()}_${msgSeq}`;
}

function createUserMessage(content) {
  return { id: nextMsgId(), role: "user", content };
}

function createAssistantMessage() {
  return { id: nextMsgId(), role: "assistant", content: "", done: false };
}

function hydrateMessages(raw) {
  const list = Array.isArray(raw) ? raw : [];
  return list.map((m, i) => ({
    id: m && m.id ? m.id : `hist_${i}`,
    role: m && m.role ? m.role : "assistant",
    content: m && typeof m.content === "string" ? m.content : "",
    done: true,
  }));
}

function scrollToBottom() {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight;
    }
  });
}

function clearChatInput() {
  inputText.value = "";
  inputKey.value++;
}

function renderMarkdown(text) {
  if (!text) return "";
  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/```([\s\S]*?)```/g, '<pre class="md-pre"><code>$1</code></pre>')
    .replace(/`([^`]+)`/g, '<code class="md-code">$1</code>')
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/\n/g, "<br/>");
  return html;
}

async function loadSessions() {
  try {
    const resp = await fetch(`${API_BASE}/sessions`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    sessionList.value = data.sessions;
  } catch {
    ElMessage.error("加载会话列表失败");
  }
}

async function registerSession(id, skills, silent = false) {
  const apiSkills = skillsToApi(skills);
  const resp = await fetch(`${API_BASE}/sessions/new`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: id,
      skills: apiSkills.length ? apiSkills : null,
    }),
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  await loadSessions();
  if (!silent) ElMessage.success("已创建新对话");
}

async function abortActiveChat() {
  if (!loading.value || !abortController) return;
  const sid = sessionId.value;
  try {
    await fetch(`${API_BASE}/sessions/${sid}/stop`, { method: "POST" });
  } catch {
    // ignore
  }
  abortController.abort();
  abortController = null;
  loading.value = false;
  streamingMsgId.value = null;
}

async function syncSessionSkills() {
  if (!sessionId.value || !isValidSessionIdFormat(sessionId.value)) return;
  try {
    const resp = await fetch(`${API_BASE}/sessions/${sessionId.value}/skills`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ skills: skillsToApi(selectedSkills.value) }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  } catch {
    ElMessage.error("技能配置保存失败");
  }
}

function handleSkillsChange() {
  if (skipSkillsChangeEmit) return;
  if (skillsSyncTimer) clearTimeout(skillsSyncTimer);
  skillsSyncTimer = setTimeout(() => {
    syncSessionSkills();
    skillsSyncTimer = null;
  }, 300);
}

async function switchSession(id) {
  if (!id || typeof id !== "string") return;
  if (id === sessionId.value) return;
  if (skillsSyncTimer) {
    clearTimeout(skillsSyncTimer);
    skillsSyncTimer = null;
  }
  await abortActiveChat();
  sessionId.value = id;
  try {
    const resp = await fetch(`${API_BASE}/sessions/${encodeURIComponent(id)}/history`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    messages.value = hydrateMessages(data.messages);
    skipSkillsChangeEmit = true;
    selectedSkills.value = skillsFromApi(data.skills || []);
    nextTick(() => {
      skipSkillsChangeEmit = false;
    });
    persistActiveSessionId(id);
  } catch {
    messages.value = [];
    ElMessage.error("加载会话失败");
  }
  scrollToBottom();
}

async function handleDeleteSession(id) {
  try {
    const resp = await fetch(`${API_BASE}/sessions/${id}`, { method: "DELETE" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    await loadSessions();
    if (id === sessionId.value) {
      await handleNewChat(true);
    }
    ElMessage.success("已删除");
  } catch {
    ElMessage.error("删除失败");
  }
}

async function handleSend() {
  const text = inputText.value.trim();
  if (!text || loading.value) return;

  messages.value.push(createUserMessage(text));
  clearChatInput();
  scrollToBottom();

  const assistantMsg = createAssistantMessage();
  messages.value.push(assistantMsg);
  streamingMsgId.value = assistantMsg.id;
  loading.value = true;
  abortController = new AbortController();

  try {
    const resp = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        session_id: sessionId.value,
        model: selectedModel.value,
      }),
      signal: abortController.signal,
    });

    if (resp.status === 409) {
      throw new Error("当前会话正在回复，请稍后再试");
    }
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let streamFinished = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const jsonStr = line.slice(6).trim();
        if (!jsonStr) continue;
        try {
          const data = JSON.parse(jsonStr);
          if (data.type === "text") {
            assistantMsg.content += data.content;
            scrollToBottom();
          } else if (data.type === "done" || data.type === "stopped") {
            streamFinished = true;
            assistantMsg.done = true;
            if (data.type === "stopped") {
              assistantMsg.content += "\n\n[已停止生成]";
            }
          } else if (data.type === "error") {
            streamFinished = true;
            assistantMsg.done = true;
            ElMessage.error(data.content);
            assistantMsg.content += `\n\n[Error: ${data.content}]`;
          }
        } catch {
          // ignore malformed json
        }
      }
    }

    if (!streamFinished) {
      assistantMsg.done = true;
    }
  } catch (e) {
    assistantMsg.done = true;
    if (e.name === "AbortError") {
      if (!assistantMsg.content.includes("[已停止生成]")) {
        assistantMsg.content += assistantMsg.content ? "\n\n[已停止生成]" : "[已停止生成]";
      }
    } else {
      ElMessage.error("请求失败: " + e.message);
      assistantMsg.content = assistantMsg.content || `[请求失败: ${e.message}]`;
    }
  } finally {
    loading.value = false;
    streamingMsgId.value = null;
    abortController = null;
    scrollToBottom();
    await loadSessions();
  }
}

async function handleStop() {
  if (!abortController) return;
  try {
    await fetch(`${API_BASE}/sessions/${sessionId.value}/stop`, { method: "POST" });
  } catch {
    // ignore
  }
  abortController.abort();
}

function handleInputKeydown(e) {
  if (e.key !== "Enter") return;
  if (e.isComposing || e.keyCode === 229) return;
  if (e.shiftKey) return;
  e.preventDefault();
  handleSend();
}

async function handleNewChat(silent = false) {
  if (skillsSyncTimer) {
    clearTimeout(skillsSyncTimer);
    skillsSyncTimer = null;
  }
  await abortActiveChat();
  const newId = generateId();
  sessionId.value = newId;
  messages.value = [];
  clearChatInput();
  try {
    await registerSession(newId, selectedSkills.value, silent);
    persistActiveSessionId(newId);
  } catch {
    ElMessage.error("创建会话失败");
  }
}

onMounted(async () => {
  try {
    await loadSessions();
    const stored = readStoredSessionId();
    const knownIds = new Set(
      sessionList.value.map((s) => s?.session_id).filter((sid) => typeof sid === "string" && sid.length > 0)
    );

    if (stored && isValidSessionIdFormat(stored) && knownIds.has(stored)) {
      await switchSession(stored);
    } else {
      if (stored) sessionStorage.removeItem(ACTIVE_SESSION_KEY);
      const first = sessionList.value[0];
      const firstId = first && typeof first.session_id === "string" ? first.session_id : "";
      if (firstId) {
        await switchSession(firstId);
      } else {
        await handleNewChat(true);
      }
    }
  } catch (e) {
    console.error(e);
    try {
      await handleNewChat(true);
    } catch (_) {
      /* ignore */
    }
  }
  scrollToBottom();
});
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  background: #ffffff;
  color: #1d1d1f;
}

.app-container {
  display: flex;
  width: 100%;
  min-height: 100vh;
  height: 100%;
  overflow: hidden;
}

.sidebar {
  width: 260px;
  background: #1a1a2e;
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  flex-shrink: 0;
}

.sidebar.collapsed {
  width: 56px;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  height: 52px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.sidebar-title {
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-toggle-btn {
  color: rgba(255, 255, 255, 0.6) !important;
}

.sidebar-toggle-btn:hover {
  color: #ffffff !important;
  background: rgba(255, 255, 255, 0.08) !important;
}

.sidebar-new-chat-wrap {
  padding: 10px 10px 6px;
  flex-shrink: 0;
}

.sidebar.collapsed .sidebar-new-chat-wrap {
  padding: 10px 6px 6px;
}

.new-chat-btn {
  font-size: 14px;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 8px 12px;
}

.session-item {
  display: flex;
  align-items: center;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.75);
  transition: background 0.15s;
  margin-bottom: 2px;
  font-size: 13px;
}

.session-item:hover {
  background: rgba(255, 255, 255, 0.08);
}

.session-item.active {
  background: rgba(64, 158, 255, 0.25);
  color: #ffffff;
}

.session-title {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.delete-btn {
  opacity: 0;
  color: rgba(255, 255, 255, 0.5) !important;
  transition: opacity 0.15s;
}

.session-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  color: #f56c6c !important;
}

.chat-layout {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: #ffffff;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 52px;
  padding: 0 20px;
  background: #ffffff;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
}

.model-select {
  width: 160px;
}

.skill-select {
  width: 180px;
}

.chat-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  background: #f7f8fa;
}

.message-list {
  height: 100%;
  overflow-y: auto;
  padding: 20px 16px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 70%;
}

.empty-icon-wrap {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  background: #ecf5ff;
}

.empty-icon {
  color: var(--el-color-primary);
}

.empty-title {
  font-size: 16px;
  font-weight: 500;
  color: #1d1d1f;
  margin-bottom: 6px;
}

.empty-hint {
  font-size: 13px;
  color: #8c8c8c;
}

.message-row {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  max-width: min(85%, 1780px);
  margin-left: auto;
  margin-right: auto;
}

.message-user {
  flex-direction: row-reverse;
}

.msg-avatar {
  flex-shrink: 0;
}

.avatar-user {
  background: var(--el-color-primary) !important;
  color: #fff !important;
}

.avatar-assistant {
  background: var(--el-color-success) !important;
  color: #fff !important;
}

.message-bubble {
  max-width: 72%;
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.6;
  font-size: 14px;
  word-break: break-word;
}

.bubble-user {
  background: var(--el-color-primary);
  color: #ffffff;
  border-top-right-radius: 4px;
}

.bubble-assistant {
  background: #ffffff;
  color: #1d1d1f;
  border: 1px solid var(--el-border-color-lighter);
  border-top-left-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.md-pre {
  margin: 10px 0;
  padding: 12px 14px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.5;
  background: #f5f7fa;
  border: 1px solid var(--el-border-color-lighter);
}

.bubble-user .md-pre {
  background: rgba(0, 0, 0, 0.2);
  border-color: rgba(255, 255, 255, 0.15);
}

.md-pre code {
  font-family: "SF Mono", "Cascadia Code", Consolas, monospace;
  color: #333;
  white-space: pre;
}

.bubble-user .md-pre code {
  color: #fff;
}

.md-code {
  font-family: "SF Mono", "Cascadia Code", Consolas, monospace;
  font-size: 0.9em;
  padding: 2px 6px;
  border-radius: 4px;
  background: #f0f2f5;
  color: #333;
}

.bubble-user .md-code {
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
}

.cursor-blink {
  display: inline-block;
  animation: blink 1s step-end infinite;
  color: var(--el-color-primary);
  font-weight: bold;
  margin-left: 2px;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

.chat-footer {
  padding: 12px 20px 16px;
  flex-shrink: 0;
  background: #ffffff;
  border-top: 1px solid var(--el-border-color-lighter);
}

.input-area {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  max-width: min(85%, 1780px);
  margin: 0 auto;
}

.input-wrapper {
  flex: 1;
  min-width: 0;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  transition: border-color 0.2s, box-shadow 0.2s;
  background: #fff;
  overflow: hidden;
}

.input-wrapper:focus-within {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 2px var(--el-color-primary-light-8);
}

.chat-input.el-textarea :deep(.el-textarea__inner) {
  background: transparent !important;
  color: #1d1d1f !important;
  border: none !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  resize: none;
  font-size: 14px;
  min-height: 38px !important;
  padding: 8px 12px;
}

.chat-input.el-textarea :deep(.el-textarea__inner:focus) {
  box-shadow: none !important;
}

.send-btn {
  flex-shrink: 0;
  height: 38px;
  min-width: 38px;
  padding: 0 10px;
  border-radius: 8px;
}

.stop-btn {
  flex-shrink: 0;
  height: 38px;
  min-width: 38px;
  padding: 0 10px;
  border-radius: 8px;
}

.stop-btn-wide {
  min-width: auto;
  padding: 0 14px;
}

.stop-label {
  margin-left: 4px;
}

.send-btn.is-disabled {
  opacity: 0.4;
}
</style>
