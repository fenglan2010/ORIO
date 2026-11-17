# 官方写入契约（示例，默认不会加载）

本目录只放契约格式说明和示例，**不会被运行时自动加载**，也不能作为生产契约安装。示例文件均带 `"example": true`，安装接口会拒绝它们。

公开资料里，酒店商家写入接口基本是合作方契约，不是可随便调用的公开路径：

- **携程**：未找到稳定、可公开引用的酒店商家调价写入 HTTP 文档。公开可见的价格同步接口属于玩乐/门票等（例如 ttdstp pricesync），不能当作酒店 eBooking 写接口使用。生产环境 URL 只能由合作方契约提供，本仓库不内置。
- **美团**：存在官方酒店直连开放平台（[openplatform-hotel.meituan.com](https://openplatform-hotel.meituan.com)），鉴权为合作方 MWS（partnerId + 签名）。公开页面提到商品/价格同步，但完整写入路径与请求体需在合作接入后按官方文档填写。不要在本仓库猜测或写死生产路径。
- **飞猪**：开放平台有公开文档。网关 `https://eco.taobao.com/router/rest`，方法如 `taobao.xhotel.rates.increment` / `taobao.xhotel.rate.update`，需 AppKey、session 与 TOP 签名。该 URL 来自官方文档，可写在示例契约中，但**默认演示不会加载、也不会自动请求该地址**。

运行时只从以下位置加载契约（需同时满足渠道已授权、服务器凭证、写入开关），且不会回退到本目录：

1. 环境变量 `OIRO_OFFICIAL_CONTRACT_CTRIP` / `_MEITUAN` / `_FLIGGY` 指向的 JSON 文件
2. 目录 `OIRO_OFFICIAL_CONTRACT_DIR/{platform}.json`
3. 服务器配置项 `official_contract_{platform}`（可由酒店管理员在设置「渠道连接」中校验后安装或卸载）

由环境变量或目录管理的契约不能从酒店界面删除，也不会删除服务器上的文件。公开状态只展示是否已配置、来源、主机名和支持的动作，不回显密钥或契约全文。

契约必须包含：`platform`、`auth`、至少一个含 `method` / `path` 的动作，以及 `base_url`（可写在根上或动作上）。非本机地址必须是 https；本机测试可用 `http://127.0.0.1` 或 `localhost`。生产环境 URL 必须来自合作方正式契约，本仓库不编造携程/美团/飞猪写入路径。
