<template>
  <div class="login-page">
    <form class="login-card" @submit.prevent="submit">
      <div class="brand" style="padding:0;min-height:auto;margin-bottom:4px">
        <div class="brand-logo"><Icon name="logo" :size="18" /></div>
        <div class="brand-text">
          <div class="brand-name">OIRO</div>
          <div class="brand-sub">运维端</div>
        </div>
      </div>
      <h1>运维配置</h1>
      <div class="sub">配置官方契约、接口地址和写入开关。酒店账号不能进入此页。</div>
      <p v-if="error" class="error">{{ error }}</p>
      <label>运维账号</label>
      <input v-model="username" autocomplete="username" />
      <label>密码</label>
      <input v-model="password" type="password" autocomplete="current-password" />
      <button class="btn btn-primary" style="width:100%;margin-top:8px" :disabled="loading" type="submit">
        {{ loading ? "登录中…" : "进入运维端" }}
      </button>
      <div class="hint">
        演示运维账号（非酒店账号）：ops / ops123<br />
        用于为本店安装合作方提供的官方契约。不会编造生产环境 URL，示例契约（example: true）不能安装，安装契约本身不会出站。<br />
        <router-link class="link" to="/login">返回酒店端登录</router-link>
      </div>
    </form>
  </div>
</template>
<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { api, setToken } from "../api/client";
import Icon from "../components/Icon.vue";

const username = ref("ops");
const password = ref("ops123");
const error = ref("");
const loading = ref(false);
const router = useRouter();

async function submit() {
  error.value = "";
  loading.value = true;
  try {
    const data = await api.opsLogin(username.value, password.value);
    setToken(data.access_token, "ops");
    router.push("/ops");
  } catch (e) {
    error.value = e.message || "登录失败";
  } finally {
    loading.value = false;
  }
}
</script>
