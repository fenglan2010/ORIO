<template>
    <div class="page-head">
      <div>
        <h1>L5 自主收益系统 - 自我进化</h1>
        <p>系统持续学习、自我优化的预览界面。以下内容为演示，不代表已上线进化引擎。</p>
      </div>
      <div class="page-actions">
        <span class="chip">进化引擎 <button class="toggle" type="button" disabled title="演示预览，不可开启"><i></i></button></span>
        <button class="btn btn-purple" type="button" disabled>进入沙盒模式</button>
      </div>
    </div>

    <div class="card card-pad" style="background:var(--purple-bg);border-color:#e9d5ff;margin-bottom:16px">
      <div class="row" style="gap:12px;align-items:flex-start">
        <div class="q-ico purple"><Icon name="spark" /></div>
        <div style="flex:1">
          <b>AI 进化系统（预览）</b>
          <p class="muted" style="margin:4px 0 0">演示故事围绕搜索排名下滑、价格倒挂与差评展开。本页不会训练模型、不会跨酒店迁移，也不会自动改价。</p>
        </div>
      </div>
      <div class="grid-4" style="margin-top:14px">
        <div class="subcard" style="background:var(--surface)"><div class="muted">展示版本</div><b>预览 v0.1</b></div>
        <div class="subcard" style="background:var(--surface)"><div class="muted">诊断覆盖</div><b>排名 / 倒挂 / 差评</b></div>
        <div class="subcard" style="background:var(--surface)"><div class="muted">人审节点</div><b>必须保留</b></div>
        <div class="subcard" style="background:var(--surface)"><div class="muted">自动调价</div><b>未启用</b></div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card card-pad">
        <div class="section-title">
          演示：指标对照曲线
          <span class="tag success">近 14 日实际</span>
        </div>
        <LineChart :series="[{ name: '转化率', values: convValues, color: '#8200db', area: true }]" :labels="labels" :area="true" :height="220" />
        <div class="notice notice-purple" style="margin-top:12px">曲线使用真实转化率，用于观察演示故事中的走弱，不是模型准确率演变。</div>
      </div>
      <div class="card card-pad">
        <div class="section-title">能力代次（示意）</div>
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
        演示因子
        <span class="phase-note">预览 / 演示</span>
      </div>
      <div class="grid-3">
        <div class="factor high">
          <div class="row" style="justify-content:space-between"><b>搜索排名下滑</b><span class="tag danger">高影响</span></div>
          <p class="muted">近一周搜索排名后移，是本轮演示主线。</p>
          <div class="bar-track" style="margin-top:10px"><span style="width:85%;background:#e7000b"></span></div>
        </div>
        <div class="factor medium">
          <div class="row" style="justify-content:space-between"><b>价格倒挂</b><span class="tag warning">中影响</span></div>
          <p class="muted">竞对降价 12%–18%，我方挂牌价基本未动。</p>
          <div class="bar-track" style="margin-top:10px"><span style="width:70%;background:#f54900"></span></div>
        </div>
        <div class="factor medium">
          <div class="row" style="justify-content:space-between"><b>差评信号</b><span class="tag warning">中影响</span></div>
          <p class="muted">存在提及噪音与卫生的低分评价，回复必须人审。</p>
          <div class="bar-track" style="margin-top:10px"><span style="width:60%;background:#f59e0b"></span></div>
        </div>
      </div>
    </div>

    <div class="space"></div>
    <div class="card card-pad">
      <div class="section-title">
        进化事件日志（示意）
        <span class="phase-note">非实时引擎</span>
      </div>
      <div class="queue-item" v-for="e in events" :key="e.t">
        <div class="meta">
          <h3>{{ e.t }} · {{ e.title }}</h3>
          <p>{{ e.body }}</p>
          <p class="impact">{{ e.result }}</p>
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
        <div class="muted" style="text-align:center;margin:6px 0">本轮不支持迁移</div>
        <div class="subcard">
          <div class="muted">目标酒店</div>
          <b>—</b>
        </div>
        <button class="btn btn-purple btn-block" type="button" disabled>一键迁移策略</button>
        <p class="muted" style="margin-top:8px">L5 跨酒店学习为后续阶段，此按钮不可用。</p>
      </div>
      <div class="card card-pad">
        <div class="section-title">伦理与风险自检</div>
        <div class="row" style="justify-content:space-between;margin:8px 0"><span>价格公平性</span><span class="tag success">约束展示中</span></div>
        <div class="row" style="justify-content:space-between;margin:8px 0"><span>客人隐私保护</span><span class="tag success">不展示密钥</span></div>
        <div class="row" style="justify-content:space-between;margin:8px 0"><span>自动调价</span><span class="tag warning">未启用</span></div>
        <p class="muted">自检底线：调价与回复必须人审；即使风险为低也不会自动执行。</p>
      </div>
      <div class="card card-pad">
        <div class="section-title">长期价值</div>
        <div v-for="r in longs" :key="r.label" style="margin-bottom:12px">
          <div class="row" style="justify-content:space-between"><span>{{ r.label }}</span><b>{{ r.val }}</b></div>
          <div class="bar-track"><span :style="{ width: r.pct + '%', background: r.color }"></span></div>
        </div>
        <p class="muted">说明性目标：短期收益与长期口碑并重。数值为示意。</p>
      </div>
    </div>
</template>

<script setup>
import { computed, inject, onMounted, ref, watch } from "vue";
import LineChart from "../components/LineChart.vue";
import Icon from "../components/Icon.vue";
import { api } from "../api/client";
import { shellState } from "../utils/shellState";

const series = ref([]);
const shell = inject("appShell", null);
const labels = computed(() => series.value.filter((p) => !p.is_future).map((p) => p.date));
const convValues = computed(() => series.value.filter((p) => !p.is_future).map((p) => Number(p.conversion_rate || 0) * 100));

const gens = [
  { id: "G1", title: "数据观察", desc: "看板、预警与竞对价格带", active: true },
  { id: "G2", title: "可解释策略", desc: "启发式定价 + 人审", active: true },
  { id: "G3", title: "竞品智能响应", desc: "规划中，不自动跟价", active: false },
  { id: "G4", title: "全域收益优化", desc: "规划中，本轮未开通", active: false },
];
const events = [
  { t: "演示设定", title: "搜索排名下滑被识别", body: "系统在 L1 形成排名下跌预警，并可生成诊断。", result: "结果：进入观察与归因，而不是自动改价" },
  { t: "演示设定", title: "价格倒挂被记录", body: "竞对降价后我方挂牌价未动，形成倒挂信号。", result: "结果：策略建议给出区间与理由，等待人审" },
  { t: "演示设定", title: "差评进入回复流程", body: "低分评价可生成回复草稿。", result: "结果：草稿必须人审，系统不会对外发送" },
];
const longs = [
  { label: "口碑与回复质量", val: "人审保护", pct: 80, color: "#8200db" },
  { label: "价格纪律", val: "上下限约束", pct: 70, color: "#155dfc" },
  { label: "市场定位", val: "按当前登录酒店", pct: 60, color: "#22c55e" },
];

async function load() {
  const t = await api.timeseries();
  series.value = t.series || [];
}
onMounted(() => load().catch(() => {}));
if (shell?.refreshTick) watch(shell.refreshTick, () => load().catch(() => {}));
</script>
