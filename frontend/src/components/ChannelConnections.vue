<template>
  <div>
    <div class="section-title">
      渠道连接
      <span class="muted" style="font-weight:500">密钥保存后不再回显</span>
    </div>
    <p class="muted" style="margin-top:0">
      连接携程、美团或飞猪后，只在设置里显示授权状态和平台酒店/账号 ID。真实写入还需要已安装的官方契约并打开写入开关。docs/official-contracts/ 里的示例不会自动加载，也不能当作生产契约安装；生产环境 URL 必须来自合作方，本仓库不会编造。没有契约时把写入模式设为 live 会被拒绝，且不会出站。渠道凭证和契约安装仅酒店管理员可操作。
    </p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="saved" class="notice notice-ok">{{ saved }}</p>
    <div v-for="ch in channels" :key="ch.platform" class="subcard" style="margin-bottom:12px">
      <div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:8px">
        <div>
          <b>{{ ch.label }}</b>
          <div class="row" style="margin-top:4px;flex-wrap:wrap;gap:6px">
            <StatusBadge :value="ch.status" :map="statusMap" />
            <span class="tag" :class="ch.contract_configured ? 'success' : ''">官方契约 {{ contractSourceLabel(ch) }}</span>
            <span class="tag" :class="ch.write_flag_enabled ? 'success' : ''">写入开关 {{ ch.write_flag_enabled ? "已开" : "未开" }}</span>
            <span v-if="ch.live_ready" class="tag success">可 live 写入</span>
          </div>
        </div>
        <div v-if="canManage" class="row" style="flex-shrink:0">
          <button class="btn btn-sm" type="button" :disabled="busy === ch.platform" @click="verify(ch)">校验</button>
          <button class="btn btn-sm" type="button" :disabled="busy === ch.platform || ch.status === 'disconnected'" @click="disconnect(ch)">断开</button>
        </div>
      </div>
      <div class="grid-3" style="margin-top:12px">
        <div class="subcard" style="background:var(--surface)"><div class="muted">平台酒店 ID</div><b>{{ ch.platform_hotel_id || "—" }}</b></div>
        <div class="subcard" style="background:var(--surface)"><div class="muted">平台账号</div><b>{{ ch.platform_account_id || "—" }}</b></div>
        <div class="subcard" style="background:var(--surface)"><div class="muted">最近校验</div><b>{{ ch.last_verified ? formatTime(ch.last_verified) : "尚未向官方校验" }}</b></div>
      </div>
      <p v-if="ch.last_error" class="muted" style="margin:8px 0 0">{{ ch.last_error }}</p>
      <div class="grid-3" style="margin-top:12px">
        <div class="subcard" style="background:var(--surface)"><div class="muted">契约来源</div><b>{{ contractSourceLabel(ch) }}</b></div>
        <div class="subcard" style="background:var(--surface)"><div class="muted">契约主机</div><b>{{ ch.contract_host || "—" }}</b></div>
        <div class="subcard" style="background:var(--surface)"><div class="muted">支持动作</div><b>{{ (ch.supported_actions && ch.supported_actions.length) ? ch.supported_actions.join("、") : "—" }}</b></div>
      </div>
      <div v-if="!compact && canManage" class="subcard" style="margin-top:12px;background:var(--surface)">
        <b>安装官方契约</b>
        <p class="muted" style="margin:6px 0 8px">粘贴或上传合作方提供的契约 JSON，先校验再安装。校验和安装都不会自动出站。文档示例（example: true）会被拒绝。</p>
        <div class="field">
          <label>契约 JSON</label>
          <textarea v-model="drafts[ch.platform].contract_json" rows="8" style="width:100%;font-family:ui-monospace,monospace;font-size:12px" placeholder='{"platform":"ctrip","base_url":"https://…","auth":"header_api_key","actions":{"apply_price":{"method":"POST","path":"/…"}}}'></textarea>
        </div>
        <div class="row" style="margin-top:8px;flex-wrap:wrap;gap:8px">
          <label class="btn btn-sm" style="margin:0">
            上传 JSON
            <input type="file" accept="application/json,.json" style="display:none" @change="onContractFile(ch, $event)" />
          </label>
          <button class="btn btn-sm" type="button" :disabled="busy === ch.platform" @click="validateContract(ch)">校验</button>
          <button class="btn btn-primary btn-sm" type="button" :disabled="busy === ch.platform" @click="installContract(ch)">安装</button>
          <button class="btn btn-sm" type="button" :disabled="busy === ch.platform || !ch.contract_configured" @click="uninstallContract(ch)">{{ ch.contract_removable ? "卸载设置契约" : "卸载" }}</button>
        </div>
      </div>
      <div v-if="!compact && canManage" class="form-grid" style="margin-top:12px">
        <div class="field">
          <label>平台酒店 / 商户 ID</label>
          <input v-model="drafts[ch.platform].platform_hotel_id" placeholder="保存后可见" />
        </div>
        <div class="field">
          <label>平台账号 ID</label>
          <input v-model="drafts[ch.platform].platform_account_id" placeholder="可选" />
        </div>
        <div class="field">
          <label>密钥</label>
          <input v-model="drafts[ch.platform].key" type="password" autocomplete="new-password" :placeholder="ch.has_credentials ? '已保存，不回显；留空则保持原密钥' : '保存后不再回显'" />
        </div>
        <div class="field">
          <label>密钥 Secret</label>
          <input v-model="drafts[ch.platform].secret" type="password" autocomplete="new-password" :placeholder="ch.has_credentials ? '已保存，不回显；留空则保持原密钥' : '保存后不再回显'" />
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
  credentials_missing: "缺少凭证",
  authorized: "已授权",
  error: "连接异常",
};
const localChannels = ref([]);
const drafts = reactive({});
const busy = ref("");
const error = ref("");
const saved = ref("");

const channels = ref([]);

function syncList(list) {
  const rows = list || [];
  channels.value = rows;
  for (const ch of rows) {
    if (!drafts[ch.platform]) {
      drafts[ch.platform] = { platform_hotel_id: "", platform_account_id: "", key: "", secret: "", contract_json: "" };
    }
    drafts[ch.platform].platform_hotel_id = ch.platform_hotel_id || "";
    drafts[ch.platform].platform_account_id = ch.platform_account_id || "";
    drafts[ch.platform].key = "";
    drafts[ch.platform].secret = "";
    if (drafts[ch.platform].contract_json == null) drafts[ch.platform].contract_json = "";
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


function contractSourceLabel(ch) {
  if (!ch || !ch.contract_configured) return "未配置";
  return { env_file: "服务器文件", settings: "已安装（设置）", none: "未配置" }[ch.contract_source] || ch.contract_source;
}
function parseDraftContract(ch) {
  const raw = (drafts[ch.platform] && drafts[ch.platform].contract_json) || "";
  if (!raw.trim()) throw new Error("请先粘贴或上传契约 JSON");
  return JSON.parse(raw);
}
async function onContractFile(ch, ev) {
  const file = ev.target.files && ev.target.files[0];
  ev.target.value = "";
  if (!file) return;
  error.value = "";
  try {
    drafts[ch.platform].contract_json = await file.text();
    saved.value = "已读入 " + file.name + "，请先校验再安装。";
  } catch (e) {
    error.value = e.message || "无法读取文件";
  }
}
async function validateContract(ch) {
  busy.value = ch.platform;
  error.value = "";
  saved.value = "";
  try {
    const contract = parseDraftContract(ch);
    const res = await api.validateChannelContract(ch.platform, contract);
    saved.value = res.message || "契约校验通过，尚未保存，也未出站。";
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = "";
  }
}
async function installContract(ch) {
  busy.value = ch.platform;
  error.value = "";
  saved.value = "";
  try {
    const contract = parseDraftContract(ch);
    const res = await api.installChannelContract(ch.platform, contract);
    drafts[ch.platform].contract_json = "";
    await loadOne(res);
    saved.value = res.message || "官方契约已安装。";
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = "";
  }
}
async function uninstallContract(ch) {
  busy.value = ch.platform;
  error.value = "";
  saved.value = "";
  try {
    const res = await api.uninstallChannelContract(ch.platform);
    await loadOne(res);
    saved.value = res.message || "已卸载官方契约。";
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = "";
  }
}

async function save(ch) {
  busy.value = ch.platform;
  error.value = "";
  saved.value = "";
  try {
    const draft = drafts[ch.platform] || {};
    const payload = {
      platform_hotel_id: draft.platform_hotel_id,
      platform_account_id: draft.platform_account_id,
    };
    if (draft.key) payload.key = draft.key;
    if (draft.secret) payload.secret = draft.secret;
    const res = await api.connectChannel(ch.platform, payload);
    await loadOne(res);
    saved.value = "连接已保存，密钥不再回显。";
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
    saved.value = res.contract_configured ? "已按官方契约完成校验。" : "凭证已保存。未配置官方契约，本次未向官方接口发请求。";
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
    saved.value = "已断开连接并清除保存的密钥。";
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
