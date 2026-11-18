<template>
  <div class="ops-page">
    <header class="ops-top">
      <div class="brand" style="padding:0;min-height:auto">
        <div class="brand-logo"><Icon name="logo" :size="18" /></div>
        <div class="brand-text">
          <div class="brand-name">OIRO 运维端</div>
          <div class="brand-sub">官方契约与写入配置</div>
        </div>
      </div>
      <div class="row" style="gap:8px">
        <span class="chip">{{ me.display_name || "运维管理员" }}</span>
        <button class="btn btn-sm" type="button" @click="logout">退出</button>
      </div>
    </header>

    <p class="muted" style="margin:0 0 16px">
      在这里为本店安装合作方提供的官方 OTA 或 PMS/CRS 契约、查看接口主机、开放动作，并配置读写开关和官方接口凭证。
      酒店只需在酒店端授权本店账号和密码。安装契约本身不会发起出站请求；示例契约（example: true）会被拒绝；本仓库不会编造生产环境 URL，也不内置可单独售卖的轻量 PMS。
    </p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="saved" class="notice notice-ok">{{ saved }}</p>

    <div class="field" style="max-width:420px;margin-bottom:16px">
      <label>选择酒店</label>
      <select v-model.number="hotelId" :disabled="!hotels.length">
        <option v-for="h in hotels" :key="h.id" :value="h.id">{{ h.name }}（{{ h.city }}）</option>
      </select>
    </div>

    <div v-if="!hotelId" class="empty">请选择酒店。</div>
    <h2 v-if="hotelId" class="section-title">OTA 渠道</h2>
    <div v-for="ch in channels" :key="ch.platform" class="card card-pad" style="margin-bottom:16px">
      <div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:8px">
        <div>
          <b>{{ ch.label }}</b>
          <div class="row" style="margin-top:4px;flex-wrap:wrap;gap:6px">
            <StatusBadge :value="ch.status" :map="statusMap" />
            <span class="tag" :class="ch.contract_enabled ? 'success' : ''">契约 {{ ch.contract_enabled ? "已启用" : "未启用" }}</span>
            <span class="tag" :class="ch.write_flag_enabled ? 'success' : ''">写入开关 {{ ch.write_flag_enabled ? "已开" : "未开" }}</span>
            <span v-if="ch.live_ready" class="tag success">可 live 写入</span>
          </div>
        </div>
      </div>
      <div class="grid-3" style="margin-top:12px">
        <div class="subcard"><div class="muted">契约来源</div><b>{{ sourceLabel(ch) }}</b></div>
        <div class="subcard"><div class="muted">契约主机</div><b>{{ ch.contract_host || "—" }}</b></div>
        <div class="subcard"><div class="muted">已开放动作</div><b>{{ (ch.action_labels || ch.open_actions || []).join("、") || "—" }}</b></div>
      </div>
      <div class="grid-3" style="margin-top:12px">
        <div class="subcard"><div class="muted">酒店已授权账号</div><b>{{ ch.has_hotel_credentials ? "是" : "否" }}</b></div>
        <div class="subcard"><div class="muted">官方接口凭证</div><b>{{ ch.has_official_credentials ? "已配置（不回显）" : "未配置" }}</b></div>
        <div class="subcard"><div class="muted">最近校验</div><b>{{ ch.last_verified || "—" }}</b></div>
      </div>
      <p v-if="ch.last_error" class="muted" style="margin:8px 0 0">{{ ch.last_error }}</p>

      <div class="subcard" style="margin-top:12px;background:var(--surface)">
        <b>写入开关与官方接口凭证</b>
        <p class="muted" style="margin:6px 0 8px">写入开关默认关闭。打开后仍须酒店已授权且官方契约已启用，才会在 live 模式下出站。官方接口密钥保存后不再回显，与酒店 OTA 账号密码分开存放。</p>
        <div class="row" style="justify-content:space-between;margin:10px 0">
          <div>
            <b>该渠道写入开关</b>
            <div class="muted">仅为运维配置，不会单独发起外部请求。</div>
          </div>
          <button type="button" class="toggle" :class="{ on: ch.write_flag_enabled }" :disabled="busy === ch.platform" @click="toggleWrite(ch)">
            <i></i>
          </button>
        </div>
        <div class="form-grid">
          <div class="field">
            <label>官方接口 Key</label>
            <input v-model="drafts[ch.platform].key" type="password" autocomplete="new-password" :placeholder="ch.has_official_credentials ? '已保存，不回显；留空则保持' : '可选，保存后不回显'" />
          </div>
          <div class="field">
            <label>官方接口 Secret</label>
            <input v-model="drafts[ch.platform].secret" type="password" autocomplete="new-password" :placeholder="ch.has_official_credentials ? '已保存，不回显；留空则保持' : '可选，保存后不回显'" />
          </div>
        </div>
        <button class="btn btn-sm" style="margin-top:8px" type="button" :disabled="busy === ch.platform" @click="saveOfficialCreds(ch)">保存官方接口凭证</button>
      </div>

      <div class="subcard" style="margin-top:12px;background:var(--surface)">
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
          <button class="btn btn-sm" type="button" :disabled="busy === ch.platform || !ch.contract_enabled" @click="uninstallContract(ch)">{{ ch.contract_removable ? "卸载设置契约" : "卸载" }}</button>
        </div>
      </div>
    </div>

    <h2 v-if="hotelId" class="section-title" style="margin-top:8px">PMS/CRS 官方接口预留</h2>
    <p v-if="hotelId" class="muted" style="margin:0 0 16px">为选定酒店安装合作方提供的正式 PMS 或 CRS 契约。这是预留接入，不是已对接某一家 PMS 产品，也不包含轻量 PMS 或房态工作台。</p>
    <div v-for="ch in pmsConnections" :key="ch.kind" class="card card-pad" style="margin-bottom:16px">
      <div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:8px">
        <div>
          <b>{{ ch.label }}</b>
          <div class="row" style="margin-top:4px;flex-wrap:wrap;gap:6px">
            <StatusBadge :value="ch.status" :map="statusMap" />
            <span class="tag" :class="ch.contract_enabled ? 'success' : ''">契约 {{ ch.contract_enabled ? "已启用" : "未启用" }}</span>
            <span class="tag" :class="ch.read_flag_enabled ? 'success' : ''">读取开关 {{ ch.read_flag_enabled ? "已开" : "未开" }}</span>
            <span class="tag" :class="ch.write_flag_enabled ? 'success' : ''">写入开关 {{ ch.write_flag_enabled ? "已开" : "未开" }}</span>
            <span v-if="ch.live_ready" class="tag success">可官方拉取</span>
          </div>
        </div>
      </div>
      <div class="grid-3" style="margin-top:12px">
        <div class="subcard"><div class="muted">契约来源</div><b>{{ sourceLabel(ch) }}</b></div>
        <div class="subcard"><div class="muted">契约主机</div><b>{{ ch.contract_host || "—" }}</b></div>
        <div class="subcard"><div class="muted">已开放动作</div><b>{{ (ch.action_labels || ch.open_actions || []).join("、") || "—" }}</b></div>
      </div>
      <div class="grid-3" style="margin-top:12px">
        <div class="subcard"><div class="muted">酒店已授权账号</div><b>{{ ch.has_hotel_credentials ? "是" : "否" }}</b></div>
        <div class="subcard"><div class="muted">官方接口凭证</div><b>{{ ch.has_official_credentials ? "已配置（不回显）" : "未配置" }}</b></div>
        <div class="subcard"><div class="muted">最近校验</div><b>{{ ch.last_verified || "—" }}</b></div>
      </div>
      <p v-if="ch.last_error" class="muted" style="margin:8px 0 0">{{ ch.last_error }}</p>

      <div class="subcard" style="margin-top:12px;background:var(--surface)">
        <b>读取 / 写入开关与官方接口凭证</b>
        <p class="muted" style="margin:6px 0 8px">读取开关默认关闭。打开后仍须已启用官方契约且有凭证，采集任务才会按契约出站拉取。官方接口密钥保存后不再回显，与酒店账号密码分开存放。</p>
        <div class="row" style="justify-content:space-between;margin:10px 0">
          <div>
            <b>该接口读取开关</b>
            <div class="muted">仅为运维配置，不会单独发起外部请求。</div>
          </div>
          <button type="button" class="toggle" :class="{ on: ch.read_flag_enabled }" :disabled="busy === ch.kind" @click="togglePmsRead(ch)">
            <i></i>
          </button>
        </div>
        <div class="row" style="justify-content:space-between;margin:10px 0">
          <div>
            <b>该接口写入开关</b>
            <div class="muted">预留推送开关，默认关闭，不会单独出站。</div>
          </div>
          <button type="button" class="toggle" :class="{ on: ch.write_flag_enabled }" :disabled="busy === ch.kind" @click="togglePmsWrite(ch)">
            <i></i>
          </button>
        </div>
        <div class="form-grid">
          <div class="field">
            <label>官方接口 Key</label>
            <input v-model="pmsDrafts[ch.kind].key" type="password" autocomplete="new-password" :placeholder="ch.has_official_credentials ? '已保存，不回显；留空则保持' : '可选，保存后不回显'" />
          </div>
          <div class="field">
            <label>官方接口 Secret</label>
            <input v-model="pmsDrafts[ch.kind].secret" type="password" autocomplete="new-password" :placeholder="ch.has_official_credentials ? '已保存，不回显；留空则保持' : '可选，保存后不回显'" />
          </div>
        </div>
        <button class="btn btn-sm" style="margin-top:8px" type="button" :disabled="busy === ch.kind" @click="savePmsOfficialCreds(ch)">保存官方接口凭证</button>
      </div>

      <div class="subcard" style="margin-top:12px;background:var(--surface)">
        <b>安装官方 PMS/CRS 契约</b>
        <p class="muted" style="margin:6px 0 8px">粘贴或上传合作方提供的契约 JSON，先校验再安装。校验和安装都不会自动出站。文档示例（example: true）会被拒绝。不要填写本仓库编造的生产主机。</p>
        <div class="field">
          <label>契约 JSON</label>
          <textarea v-model="pmsDrafts[ch.kind].contract_json" rows="8" style="width:100%;font-family:ui-monospace,monospace;font-size:12px" placeholder='{"platform":"pms","base_url":"https://…","auth":"header_api_key","actions":{"pull_inventory":{"method":"GET","path":"/…","kind":"read"}}}'></textarea>
        </div>
        <div class="row" style="margin-top:8px;flex-wrap:wrap;gap:8px">
          <label class="btn btn-sm" style="margin:0">
            上传 JSON
            <input type="file" accept="application/json,.json" style="display:none" @change="onPmsContractFile(ch, $event)" />
          </label>
          <button class="btn btn-sm" type="button" :disabled="busy === ch.kind" @click="validatePmsContract(ch)">校验</button>
          <button class="btn btn-primary btn-sm" type="button" :disabled="busy === ch.kind" @click="installPmsContract(ch)">安装</button>
          <button class="btn btn-sm" type="button" :disabled="busy === ch.kind || !ch.contract_enabled" @click="uninstallPmsContract(ch)">{{ ch.contract_removable ? "卸载设置契约" : "卸载" }}</button>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { api, setToken } from "../api/client";
import Icon from "../components/Icon.vue";
import StatusBadge from "../components/StatusBadge.vue";

const router = useRouter();
const me = ref({});
const hotels = ref([]);
const hotelId = ref(0);
const channels = ref([]);
const pmsConnections = ref([]);
const drafts = reactive({});
const pmsDrafts = reactive({});
const busy = ref("");
const error = ref("");
const saved = ref("");
const statusMap = {
  disconnected: "未连接",
  credentials_missing: "未连接",
  authorized: "已连接",
  error: "连接异常",
};

function sourceLabel(ch) {
  if (!ch || !ch.contract_enabled) return "未配置";
  return { env_file: "服务器文件", settings: "已安装（设置）", none: "未配置" }[ch.contract_source] || ch.contract_source;
}

function ensureDraft(platform) {
  if (!drafts[platform]) drafts[platform] = { contract_json: "", key: "", secret: "" };
}

function ensurePmsDraft(kind) {
  if (!pmsDrafts[kind]) pmsDrafts[kind] = { contract_json: "", key: "", secret: "" };
}

async function loadHotels() {
  const data = await api.opsHotels();
  hotels.value = data.hotels || [];
  if (!hotelId.value && hotels.value.length) hotelId.value = hotels.value[0].id;
}

async function loadChannels() {
  if (!hotelId.value) {
    channels.value = [];
    pmsConnections.value = [];
    return;
  }
  const data = await api.opsChannels(hotelId.value);
  channels.value = data.channels || [];
  for (const ch of channels.value) {
    ensureDraft(ch.platform);
    drafts[ch.platform].key = "";
    drafts[ch.platform].secret = "";
  }
  const pms = await api.opsPms(hotelId.value);
  pmsConnections.value = pms.connections || [];
  for (const ch of pmsConnections.value) {
    ensurePmsDraft(ch.kind);
    pmsDrafts[ch.kind].key = "";
    pmsDrafts[ch.kind].secret = "";
  }
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
    ensureDraft(ch.platform);
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
    const res = await api.opsValidateContract(hotelId.value, ch.platform, contract);
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
    const res = await api.opsInstallContract(hotelId.value, ch.platform, contract);
    drafts[ch.platform].contract_json = "";
    await loadChannels();
    saved.value = res.message || "官方契约已安装。安装本身不会出站。";
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
    const res = await api.opsUninstallContract(hotelId.value, ch.platform);
    await loadChannels();
    saved.value = res.message || "已卸载官方契约。";
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = "";
  }
}

async function toggleWrite(ch) {
  busy.value = ch.platform;
  error.value = "";
  saved.value = "";
  try {
    await api.opsWriteFlag(hotelId.value, ch.platform, !ch.write_flag_enabled);
    await loadChannels();
    saved.value = "写入开关已更新，不会单独发起外部请求。";
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = "";
  }
}

async function saveOfficialCreds(ch) {
  busy.value = ch.platform;
  error.value = "";
  saved.value = "";
  try {
    const draft = drafts[ch.platform] || {};
    const payload = {};
    if (draft.key) payload.key = draft.key;
    if (draft.secret) payload.secret = draft.secret;
    if (!payload.key && !payload.secret) throw new Error("请输入要保存的官方接口凭证，或留空保持原值");
    await api.opsOfficialCredentials(hotelId.value, ch.platform, payload);
    drafts[ch.platform].key = "";
    drafts[ch.platform].secret = "";
    await loadChannels();
    saved.value = "官方接口凭证已保存，不再回显。";
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = "";
  }
}


function parsePmsDraftContract(ch) {
  const raw = (pmsDrafts[ch.kind] && pmsDrafts[ch.kind].contract_json) || "";
  if (!raw.trim()) throw new Error("请先粘贴或上传契约 JSON");
  return JSON.parse(raw);
}

async function onPmsContractFile(ch, ev) {
  const file = ev.target.files && ev.target.files[0];
  ev.target.value = "";
  if (!file) return;
  error.value = "";
  try {
    ensurePmsDraft(ch.kind);
    pmsDrafts[ch.kind].contract_json = await file.text();
    saved.value = "已读入 " + file.name + "，请先校验再安装。";
  } catch (e) {
    error.value = e.message || "无法读取文件";
  }
}

async function validatePmsContract(ch) {
  busy.value = ch.kind;
  error.value = "";
  saved.value = "";
  try {
    const contract = parsePmsDraftContract(ch);
    const res = await api.opsValidatePmsContract(hotelId.value, ch.kind, contract);
    saved.value = res.message || "契约校验通过，尚未保存，也未出站。";
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = "";
  }
}

async function installPmsContract(ch) {
  busy.value = ch.kind;
  error.value = "";
  saved.value = "";
  try {
    const contract = parsePmsDraftContract(ch);
    const res = await api.opsInstallPmsContract(hotelId.value, ch.kind, contract);
    pmsDrafts[ch.kind].contract_json = "";
    await loadChannels();
    saved.value = res.message || "官方 PMS/CRS 契约已安装。安装本身不会出站。";
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = "";
  }
}

async function uninstallPmsContract(ch) {
  busy.value = ch.kind;
  error.value = "";
  saved.value = "";
  try {
    const res = await api.opsUninstallPmsContract(hotelId.value, ch.kind);
    await loadChannels();
    saved.value = res.message || "已卸载官方 PMS/CRS 契约。";
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = "";
  }
}

async function togglePmsRead(ch) {
  busy.value = ch.kind;
  error.value = "";
  saved.value = "";
  try {
    await api.opsPmsReadFlag(hotelId.value, ch.kind, !ch.read_flag_enabled);
    await loadChannels();
    saved.value = "读取开关已更新，不会单独发起外部请求。";
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = "";
  }
}

async function togglePmsWrite(ch) {
  busy.value = ch.kind;
  error.value = "";
  saved.value = "";
  try {
    await api.opsPmsWriteFlag(hotelId.value, ch.kind, !ch.write_flag_enabled);
    await loadChannels();
    saved.value = "写入开关已更新，不会单独发起外部请求。";
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = "";
  }
}

async function savePmsOfficialCreds(ch) {
  busy.value = ch.kind;
  error.value = "";
  saved.value = "";
  try {
    const draft = pmsDrafts[ch.kind] || {};
    const payload = {};
    if (draft.key) payload.key = draft.key;
    if (draft.secret) payload.secret = draft.secret;
    if (!payload.key && !payload.secret) throw new Error("请输入要保存的官方接口凭证，或留空保持原值");
    await api.opsPmsOfficialCredentials(hotelId.value, ch.kind, payload);
    pmsDrafts[ch.kind].key = "";
    pmsDrafts[ch.kind].secret = "";
    await loadChannels();
    saved.value = "官方接口凭证已保存，不再回显。";
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = "";
  }
}

function logout() {
  setToken("");
  router.push("/ops/login");
}

watch(hotelId, () => { loadChannels().catch((e) => { error.value = e.message; }); });

onMounted(async () => {
  try {
    me.value = await api.opsMe();
    await loadHotels();
    await loadChannels();
  } catch (e) {
    error.value = e.message;
  }
});
</script>
