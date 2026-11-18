<template>
    <div class="page-head">
      <div>
        <h1>L5 本店经验沉淀</h1>
        <p>本页展示当前酒店已执行或已否决的决策摘要。跨店学习已开始，但是匿名模式，不展示其他酒店名称，不会训练模型，不会自动改价。</p>
      </div>
      <div class="page-actions">
        <span class="chip">进化引擎 <button class="toggle" type="button" disabled title="进化引擎未接通，不会训练模型，不可开启"><i></i></button></span>
        <button class="btn btn-purple" type="button" disabled>进入沙盒模式</button>
      </div>
    </div>

    <div class="card card-pad" style="background:var(--purple-bg);border-color:#e9d5ff;margin-bottom:16px">
      <div class="row" style="gap:12px;align-items:flex-start">
        <div class="q-ico purple"><Icon name="spark" /></div>
        <div style="flex:1">
          <b>本店经验沉淀与匿名跨店学习</b>
          <p class="muted" style="margin:4px 0 0">人审通过并执行，或人审否决后，会在本店留下一条可复查的决策记录，供后续建议引用。已执行的调价或活动，会在入住日实现或在手订单变化后，对照决策时基线做观察复盘；观察变化不是因果收入，也不是上年同期。跨店学习已开始，但是匿名模式，不展示其他酒店名称，不会训练模型，不会自动改价，也不会跳过人审。</p>
        </div>
      </div>
      <div class="grid-4" style="margin-top:14px">
        <div class="subcard" style="background:var(--surface)"><div class="muted">记录范围</div><b>本店经验仅当前酒店</b></div>
        <div class="subcard" style="background:var(--surface)"><div class="muted">跨店学习</div><b>匿名模式引用</b></div>
        <div class="subcard" style="background:var(--surface)"><div class="muted">人审节点</div><b>必须保留</b></div>
        <div class="subcard" style="background:var(--surface)"><div class="muted">自动调价</div><b>未启用</b></div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card card-pad">
        <div class="section-title">
          近 14 日实际转化率
          <span class="tag success">当前酒店真实指标</span>
        </div>
        <LineChart :series="[{ name: '转化率', values: convValues, color: '#8200db', area: true }]" :labels="labels" :area="true" :height="220" />
        <div class="notice notice-purple" style="margin-top:12px">曲线使用本店近 14 日实际转化率，用于观察走弱，不是模型准确率，也不代表这次调价带来了多少收入。</div>
      </div>
      <div class="card card-pad">
        <div class="section-title">能力代次</div>
        <div class="tree-item" v-for="g in gens" :key="g.id" :class="{ active: g.active }">
          <div class="gen">{{ g.id }}</div>
          <div class="grow">
            <b>{{ g.title }}</b>
            <div class="muted">{{ g.desc }}</div>
          </div>
          <span class="tag" :class="g.active ? 'info' : 'rejected'">{{ g.active ? "当前产品" : "规划中" }}</span>
        </div>
        <button class="btn btn-purple btn-block" type="button" disabled>发明新策略（未接通）</button>
      </div>
    </div>

    <div class="space"></div>
    <div class="card card-pad">
      <div class="section-title">
        本店经验记录
        <span class="phase-note">对照决策时基线观察，不是因果收入</span>
      </div>
      <p v-if="loadError" class="muted">{{ loadError }}</p>
      <div v-else-if="!memories.length" class="muted" style="padding:8px 0 4px">
        暂无已沉淀的本店决策。生成策略并完成人审（通过后执行，或否决）后，会在这里留下记录。已执行的调价可在入住日后对照基线复盘。
      </div>
      <div class="queue-item" v-for="e in memories" :key="e.id">
        <div class="meta">
          <h3>{{ formatStamp(e.created_at) }} · {{ e.action_kind_label || "决策" }} · {{ e.status_label || e.approval_status }}</h3>
          <p>{{ e.summary }}</p>
          <p class="muted" v-if="detailLine(e)">{{ detailLine(e) }}</p>
          <div v-if="hasObservedImpact(e)" class="impact-review">
            <b>{{ impactTitle(e) }}</b>
            <p class="muted">{{ (e.impact && e.impact.label) || "相对决策时基线的观察变化，不是因果收入。" }}</p>
            <div v-if="e.impact && e.impact.realized" class="subcard" style="margin-top:8px">
              <div class="muted">已实现入住日（{{ e.impact.realized.date_from }} 至 {{ e.impact.realized.date_to }}）</div>
              <p>{{ sliceLine(e.impact.realized, { revenue: true }) }}</p>
            </div>
            <div v-if="e.impact && e.impact.otb_pickup" class="subcard" style="margin-top:8px">
              <div class="muted">在手订单变化 / OTB pickup（不是已实现客房收入，也不是预测）</div>
              <p>{{ sliceLine(e.impact.otb_pickup, { revenue: false }) }}</p>
            </div>
            <p v-if="scenarioLine(e)" class="muted" style="margin-top:8px">{{ scenarioLine(e) }}</p>
          </div>
          <p v-else class="impact">{{ unmeasuredText(e) }}</p>
        </div>
      </div>
    </div>

    <div class="space"></div>
    <div class="card card-pad">
      <div class="section-title">
        匿名行业模式 / 跨店学习
        <span class="phase-note">匿名模式引用，不复制其他酒店的在用策略</span>
      </div>
      <p class="muted" style="margin:0 0 12px">跨店学习已开始，但是匿名模式，不展示其他酒店名称，不会训练模型，不会自动改价。只有至少两家酒店贡献了相同的匿名特征时，才会在这里展示。</p>
      <p v-if="patternError" class="muted">{{ patternError }}</p>
      <div v-else-if="!patterns.length" class="muted" style="padding:8px 0 4px">
        暂无可见的匿名行业模式。本店经验仍只属于当前酒店；不会出现其他酒店的名称或身份信息。
      </div>
      <div class="queue-item" v-for="p in patterns" :key="p.pattern_key">
        <div class="meta">
          <h3>{{ p.action_kind_label || "决策" }} · {{ p.status_label || p.terminal_status }}<template v-if="p.price_direction"> · 价格方向：{{ p.price_direction }}</template></h3>
          <p>{{ p.summary }}</p>
          <p class="muted" v-if="patternDetail(p)">{{ patternDetail(p) }}</p>
          <p class="impact">结果影响：尚未测算</p>
        </div>
      </div>
    </div>

    <div class="space"></div>
    <div class="grid-3">
      <div class="card card-pad">
        <div class="section-title">跨系统迁移</div>
        <div class="subcard" style="background:var(--purple-soft)">
          <div class="muted">源酒店</div>
          <b>{{ shellState.me.hotel_name || "当前酒店" }}</b>
        </div>
        <div class="muted" style="text-align:center;margin:6px 0">一键迁移不开放，以免带出其他酒店身份</div>
        <div class="subcard">
          <div class="muted">目标酒店</div>
          <b>—</b>
        </div>
        <button class="btn btn-purple btn-block" type="button" disabled>一键迁移策略</button>
        <p class="muted" style="margin-top:8px">一键迁移不开放，以免带出其他酒店身份。跨店学习只提供匿名模式引用，不会复制其他酒店的在用策略。</p>
      </div>
      <div class="card card-pad">
        <div class="section-title">伦理与风险自检</div>
        <div class="row" style="justify-content:space-between;margin:8px 0"><span>价格公平性</span><span class="tag success">约束展示中</span></div>
        <div class="row" style="justify-content:space-between;margin:8px 0"><span>客人隐私保护</span><span class="tag success">不展示密钥</span></div>
        <div class="row" style="justify-content:space-between;margin:8px 0"><span>自动调价</span><span class="tag warning">未启用</span></div>
        <p class="muted">自检底线：调价与回复必须人审；经验沉淀和匿名行业模式都不会跳过人审，也不会自动执行。</p>
      </div>
      <div class="card card-pad">
        <div class="section-title">长期价值</div>
        <div v-for="r in longs" :key="r.label" style="margin-bottom:12px">
          <div class="row" style="justify-content:space-between"><span>{{ r.label }}</span><b>{{ r.val }}</b></div>
          <div class="bar-track"><span :style="{ width: r.pct + '%', background: r.color }"></span></div>
        </div>
        <p class="muted">说明性目标：短期收益与长期口碑并重。数值为示意，不是测算结果。</p>
      </div>
    </div>
</template>

<script setup>
import { computed, inject, onMounted, ref, watch } from "vue";
import LineChart from "../components/LineChart.vue";
import Icon from "../components/Icon.vue";
import { api } from "../api/client";
import { shellState } from "../utils/shellState";
import { formatDate, pct, signed, yen } from "../utils/format";

const series = ref([]);
const memories = ref([]);
const patterns = ref([]);
const loadError = ref("");
const patternError = ref("");
const shell = inject("appShell", null);
const labels = computed(() => series.value.filter((p) => !p.is_future).map((p) => p.date));
const convValues = computed(() => series.value.filter((p) => !p.is_future).map((p) => Number(p.conversion_rate || 0) * 100));

const gens = [
  { id: "G1", title: "数据观察", desc: "看板、预警与竞对价格带", active: true },
  { id: "G2", title: "可解释策略", desc: "启发式定价 + 人审", active: true },
  { id: "G3", title: "本店经验沉淀", desc: "记录本店已执行或已否决的决策", active: true },
  { id: "G4", title: "跨酒店学习", desc: "匿名模式引用，不迁移策略，不训练模型", active: true },
  { id: "G5", title: "决策后观察", desc: "对照决策时基线观察变化，不是进化引擎，不是因果收入", active: true },
];
const longs = [
  { label: "口碑与回复质量", val: "人审保护", pct: 80, color: "#8200db" },
  { label: "价格纪律", val: "上下限约束", pct: 70, color: "#155dfc" },
  { label: "市场定位", val: "按当前登录酒店", pct: 60, color: "#22c55e" },
];

function formatStamp(value) {
  return formatDate(value) || "—";
}


function impactTitle(e) {
  if (e.action_kind === "campaign") return "这次活动实际带来了什么";
  return "这次调价实际带来了什么";
}

function hasObservedImpact(e) {
  const outcome = e?.outcome;
  const impact = e?.impact;
  if (outcome !== "measured" && outcome !== "partially_measured") return false;
  if (!impact || typeof impact !== "object") return false;
  return Boolean(impact.realized || impact.otb_pickup);
}

function unmeasuredText(e) {
  const title = impactTitle(e);
  const status = e?.approval_status || "";
  if (["rejected", "execution_failed", "rolled_back"].includes(status)) {
    return `${title}：未进入已执行状态，不自动复盘。`;
  }
  if (e?.action_kind === "review_reply") {
    return "评价回复不按调价入住窗口自动复盘。";
  }
  return `${title}：尚未复盘。等待入住日实现或后续在手订单变化。`;
}

function sliceLine(slice, { revenue } = { revenue: true }) {
  if (!slice) return "";
  const cur = slice.current_kpis || {};
  const delta = slice.delta || {};
  const bits = [];
  if (revenue && cur.revenue != null) {
    bits.push(`客房收入 ${yen(cur.revenue)}，相对基线 ${signed(delta.revenue_abs || 0, " 元", 0)}（${signed(delta.revenue_pct || 0, "%")}）`);
  }
  if (cur.occupancy != null) {
    bits.push(`出租率 ${pct(cur.occupancy)}，相对基线 ${signed(delta.occupancy_pp || 0, " 个百分点")}`);
  }
  if (cur.sold_rooms != null) {
    bits.push(`已售/在手 ${cur.sold_rooms} 间夜，相对基线 ${signed(delta.sold_rooms_abs || 0, " 间夜", 0)}`);
  }
  if (cur.adr != null && revenue) {
    bits.push(`ADR ${yen(cur.adr, 1)}，相对基线 ${signed(delta.adr_abs || 0, " 元", 1)}`);
  }
  if (cur.orders != null && !revenue) {
    bits.push(`在手订单 ${cur.orders} 单，相对基线 ${signed(delta.orders_abs || 0, " 单", 0)}`);
  }
  return bits.join("；") || (slice.label || "");
}

function scenarioLine(e) {
  const cmp = e?.impact?.scenario_comparison;
  if (!cmp || !cmp.recorded_scenario) return "";
  const rec = cmp.recorded_scenario;
  const obs = cmp.observed || {};
  const bits = ["建议情景对照（不是评分，也不是承诺兑现）"];
  if (cmp.compared_slice) bits.push(`切片：${cmp.compared_slice}`);
  if (rec.occupancy_delta_pct != null && obs.occupancy_delta_pct != null) {
    bits.push(`出租率情景 ${signed(rec.occupancy_delta_pct, " 个百分点")}，观察 ${signed(obs.occupancy_delta_pct, " 个百分点")}`);
  }
  if (rec.revenue_delta != null && obs.revenue_delta != null) {
    bits.push(`客房收入情景 ${signed(rec.revenue_delta, " 元", 0)}，观察 ${signed(obs.revenue_delta, " 元", 0)}`);
  }
  return bits.join(" · ");
}

function detailLine(e) {
  const bits = [];
  if (e.room_name) bits.push(e.room_name);
  if (e.date_from && e.date_to) bits.push(`${e.date_from} 至 ${e.date_to}`);
  else if (e.date_from) bits.push(e.date_from);
  if (e.risk_level) bits.push(`风险${({ low: "低", medium: "中", high: "高" })[e.risk_level] || e.risk_level}`);
  if (e.actor) bits.push(e.actor);
  return bits.join(" · ");
}

function patternDetail(p) {
  const bits = [];
  const signalLabels = {
    rank_drop: "排名下跌",
    price_inversion: "价格倒挂",
    conversion_drop: "转化走弱",
    competitor_cut: "竞对降价",
    negative_review: "差评信号",
  };
  const signals = (p.signal_types || []).map((s) => signalLabels[s] || s);
  if (signals.length) bits.push(signals.join("、"));
  if (p.risk_level) bits.push(`风险${({ low: "低", medium: "中", high: "高" })[p.risk_level] || p.risk_level}`);
  if (p.positioning_bucket) bits.push(`${p.positioning_bucket}定位`);
  if (p.peer_hotel_count) bits.push(`来自其他 ${p.peer_hotel_count} 家同类酒店的匿名记录`);
  if (p.peer_episode_count) bits.push(`${p.peer_episode_count} 条同模式片段`);
  return bits.join(" · ");
}

async function load() {
  loadError.value = "";
  patternError.value = "";
  const t = await api.timeseries();
  series.value = t.series || [];
  try {
    const body = await api.memories("limit=50");
    memories.value = body.memories || [];
  } catch (err) {
    memories.value = [];
    loadError.value = err?.message || "无法加载本店经验记录";
  }
  try {
    const body = await api.industryPatterns("limit=50");
    patterns.value = body.patterns || [];
  } catch (err) {
    patterns.value = [];
    patternError.value = err?.message || "无法加载匿名行业模式";
  }
}
onMounted(() => load().catch(() => {}));
if (shell?.refreshTick) watch(shell.refreshTick, () => load().catch(() => {}));
</script>
