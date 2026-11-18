<template>
  <div>
    <div class="section-title">
      渠道连接
      <span class="muted" style="font-weight:500">账号密码保存后不再回显</span>
    </div>
    <p class="muted" style="margin-top:0">
      酒店只需授权本店 OTA 账号和密码；官方契约和接口由运维端配置。连接后，这里只显示连接状态、官方契约是否已启用，以及已开放的动作（例如调价、活动）。打开 live 仍要等契约已启用；没有启用契约时改为 live 会被拒绝，且不会出站。账号密码只保存在服务器，保存后不再回显。
    </p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="saved" class="notice notice-ok">{{ saved }}</p>
    <div v-for="ch in channels" :key="ch.platform" class="subcard" style="margin-bottom:12px">
      <div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:8px">
        <div>
          <b>{{ ch.label }}</b>
          <div class="row" style="margin-top:4px;flex-wrap:wrap;gap:6px">
            <StatusBadge :value="ch.status" :map="statusMap" />
            <span class="tag" :class="ch.contract_enabled ? 'success' : ''">官方契约 {{ ch.contract_enabled ? "已启用" : "未启用" }}</span>
          </div>
        </div>
        <div v-if="canManage" class="row" style="flex-shrink:0">
          <button class="btn btn-sm" type="button" :disabled="busy === ch.platform" @click="verify(ch)">校验</button>
          <button class="btn btn-sm" type="button" :disabled="busy === ch.platform || ch.status === 'disconnected'" @click="disconnect(ch)">断开</button>
        </div>
      </div>
      <div class="grid-3" style="margin-top:12px">
        <div class="subcard" style="background:var(--surface)"><div class="muted">最近校验</div><b>{{ ch.last_verified ? formatTime(ch.last_verified) : "尚未校验" }}</b></div>
        <div class="subcard" style="background:var(--surface)"><div class="muted">官方契约</div><b>{{ ch.contract_enabled ? "已启用" : "未启用" }}</b></div>
        <div class="subcard" style="background:var(--surface)"><div class="muted">已开放动作</div><b>{{ actionText(ch) }}</b></div>
      </div>
      <p v-if="ch.last_error" class="muted" style="margin:8px 0 0">{{ ch.last_error }}</p>
      <div v-if="!compact && canManage" class="form-grid" style="margin-top:12px">
        <div class="field">
          <label>OTA 账号</label>
          <input v-model="drafts[ch.platform].account" autocomplete="off" :placeholder="ch.has_credentials ? '已保存，不回显；留空则保持原账号' : '本店在该平台的账号'" />
        </div>
        <div class="field">
          <label>OTA 密码</label>
          <input v-model="drafts[ch.platform].password" type="password" autocomplete="new-password" :placeholder="ch.has_credentials ? '已保存，不回显；留空则保持原密码' : '保存后不再回显'" />
        </div>
      </div>
      <div v-if="!compact && canManage" class="row" style="margin-top:10px">
        <button class="btn btn-primary btn-sm" type="button" :disabled="busy === ch.platform" @click="save(ch)">
          {{ busy === ch.platform ? "保存中…" : (ch.status === "disconnected" ? "连接并保存" : "保存连接") }}
        </button>
      </div>
    </div>
    <div v-if="!compact" v-for="name in laterChannels" :key="name" class="subcard">
      <div class="row" style="justify-content:space-between">
        <div>
          <b>{{ name }}</b>
          <div class="row" style="margin-top:4px"><span class="tag">后续阶段未接通</span></div>
        </div>
        <button class="btn btn-primary btn-sm" type="button" disabled>连接</button>
      </div>
    </div>
  </div>
</template>
<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { api } from "../api/client";
import StatusBadge from "./StatusBadge.vue";
import { can } from "../utils/permissions";

const props = defineProps({
  items: { type: Array, default: null },
  compact: { type: Boolean, default: false },
});
const emit = defineEmits(["refresh"]);

const canManage = computed(() => can("manage_channels"));
const laterChannels = ["Booking.com", "Agoda"];
const statusMap = {
  disconnected: "未连接",
  credentials_missing: "未连接",
  authorized: "已连接",
  error: "连接异常",
};
const localChannels = ref([]);
const drafts = reactive({});
const busy = ref("");
const error = ref("");
const saved = ref("");
const channels = ref([]);

function actionText(ch) {
  const labels = (ch && (ch.open_actions || ch.supported_actions)) || [];
  return labels.length ? labels.join("、") : "—";
}

function syncList(list) {
  const rows = list || [];
  channels.value = rows;
  for (const ch of rows) {
    if (!drafts[ch.platform]) {
      drafts[ch.platform] = { account: "", password: "" };
    }
    drafts[ch.platform].account = "";
    drafts[ch.platform].password = "";
  }
}

function formatTime(value) {
  if (!value) return "";
  const d = new Date(value.endsWith("Z") || value.includes("+") ? value : value + "Z");
  if (Number.isNaN(d.getTime())) return value;
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

async function refresh() {
  if (props.items != null) {
    syncList(props.items);
    emit("refresh");
    return;
  }
  const data = await api.channels();
  localChannels.value = data.channels || [];
  syncList(localChannels.value);
}

async function save(ch) {
  busy.value = ch.platform;
  error.value = "";
  saved.value = "";
  try {
    const draft = drafts[ch.platform] || {};
    const payload = {};
    if (draft.account) payload.account = draft.account;
    if (draft.password) payload.password = draft.password;
    if (!payload.account && !payload.password && ch.status === "disconnected") {
      throw new Error("请输入本店 OTA 账号和密码");
    }
    const res = await api.connectChannel(ch.platform, payload);
    await loadOne(res);
    saved.value = "连接已保存，账号密码不再回显。";
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = "";
  }
}

async function verify(ch) {
  busy.value = ch.platform;
  error.value = "";
  saved.value = "";
  try {
    const res = await api.verifyChannel(ch.platform);
    await loadOne(res);
    saved.value = res.contract_enabled ? "已按官方契约完成校验。" : "账号已保存。运维端尚未启用官方契约，本次未向官方接口发请求。";
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = "";
  }
}

async function disconnect(ch) {
  busy.value = ch.platform;
  error.value = "";
  saved.value = "";
  try {
    const res = await api.disconnectChannel(ch.platform);
    await loadOne(res);
    saved.value = "已断开连接并清除保存的账号密码。";
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = "";
  }
}

async function loadOne(row) {
  if (props.items != null) {
    emit("refresh");
    return;
  }
  await refresh();
  if (row) {
    channels.value = channels.value.map((c) => (c.platform === row.platform ? row : c));
  }
}

watch(() => props.items, (v) => { if (v) syncList(v); }, { immediate: true });

onMounted(async () => {
  if (props.items != null) return;
  try { await refresh(); } catch (e) { error.value = e.message; }
});
</script>
