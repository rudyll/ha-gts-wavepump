# 狗头鲨 GTS L20 造浪泵 — 通信协议分析

分析对象：GTS AQUA 安卓版 v1.2.7（包名 `com.goutousha.zaolang`，重庆狗头鲨科技），
官方应用宝渠道下载，MD5 `15ab225bd2197f57344f6173619f42a4`。
App 用 uni-app 框架，业务逻辑在未加密的 `app-service.js` 里，直接可读。
目的：评估能否用 Home Assistant / 第三方本地控制，优先本地协议。

---

## 1. 总体架构

设备有**两条控制通道，用的是同一套应用层帧**：

| 通道 | 用途 | 是否碰云 | 对网络安全 |
|------|------|----------|-----------|
| **BLE 透传串口** | 配网 + 直接控制 | 否，蓝牙点对点 | ✅ 推荐，设备无需联网 |
| **阿里云 MQTT** | 远程控制 + 状态上报 | 是，全程经厂家云 | ⚠️ 需连公网、用 App 内置密钥 |

关键点：App 里 `requestBLEDevice()` 和 MQTT 的 `Yh()` 调的是同一个指令构造逻辑，
`[250, 接口号, ...数据, 校验和]` 这套帧在蓝牙和 MQTT 上**完全一致**。
因此本地 BLE 路线不需要破解云端，也不需要任何密钥。

局域网实测：泵在 10.10.10.125 上线，但不开任何 TCP/UDP 服务端口（80 口直接拒绝连接，
无 HTTP / MQTT / 涂鸦 6668 / 本地 UDP 广播）。**Wi-Fi 侧没有本地协议**，Wi-Fi 只用于连阿里云。
本地化只能走 BLE。

---

## 2. 帧格式（请求与响应通用）

```
字节:  [0]    [1]       [2..n-2]      [n-1]
       0xFA   接口号     数据          校验和
       (250)  interface  payload       checksum
```

- 头字节固定 `250` (0xFA)。
- 第 2 字节是**接口号**（见 §4），决定这帧是什么操作。
- 中间是数据，长度随接口而定。
- 末字节是校验和。

响应帧同样以 `250` 开头，第 2 字节回带请求的接口号用于配对；
末字节要么是校验和，要么是 `255`（表示"无错误"的占位）。

## 3. 校验和

```js
checksum = (所有前置字节之和) % 255
```

源码：`Xc = e => { let t=0; for (let n=0;n<e.length;n++) t+=e[n]; return t%255 }`

校验时：末字节 `== 255` 视为合法，或 `== Xc(前面所有字节)` 视为合法。

---

## 4. 接口号（interface id）

| 接口号 | 符号 | 操作 | 说明 |
|-------|------|------|------|
| 1 | tu | 写单个配置项 | 数据 = `[字段号, 值]`，响应回 `[250,1,字段号,值,校验]`（len 5）|
| 2 | nu | 读全部配置 | 一次性返回所有字段（按顺序排布）|
| 3 | iu | 心跳/状态 | 返回当前运行状态（见 §6），响应 len 10 |
| 4 | ou | （BLE 专用）| 配网相关，数据含 SSID+`\r\n`+密码 |
| 6 | ru | 对时 | 下发当前时间 |
| 9 | au | OTA 升级 | 固件升级 |
| 10 | su | 读配置 V2 | 用 TLV 方式返回（软件版本 >4 的新机）|

设备按 `software_version` 分新老两套编码：
- `software_version <= 4`：旧版，用 §5 的 `Zc` 字段号表。
- `software_version > 4`：新版，用 `Jc` 表（每个字段有独立的 req/res 号）。

MQTT 下主题也区分：`req_update_config` / `req_config` / `req_config_time` /
`req_ota_update` / `req_updata_config_v2`（原文拼写如此）。

## 5. 字段表（写配置用）

单项写入：`写 {字段名: 值}` → 帧 `[250, 1, 字段号, 值, checksum]`。

**旧版 Zc（字段名 → 字段号）节选：**

| 字段名 | 号 | 含义 |
|--------|----|----|
| master_or_slave | 1 | 主/从机 |
| manual_or_auto | 2 | 手动 / 自动模式 |
| manual_mode | 3 | 手动子模式 |
| manual_power | 4 | 手动功率（强度）|
| manual_period | 5 | 手动周期 |
| auto_m_00 … auto_m_23 | 6,9,12…76 | 自动曲线第 0–23 段的模式 |
| auto_p_00 … auto_p_23 | 7,10,13…77 | 各段功率 |
| auto_t_00 … auto_t_23 | 8,11,14…78 | 各段时间 |
| forward_or_reverse | 79 | 正转 / 反转 |
| communication_channel | 80 | 通信通道 |

即造浪泵核心可控项：**开关/主从、手动强度、手动周期、24 段自动造浪曲线（每段 模式/强度/时间）、正反转。**
（注：Zc 表里 `auto_t_13` 号为 32，与 `auto_t_08` 重复，疑似厂家笔误；另有一个
`error_filed_if_see_contact_developer:44` 占位，实施时按新版 Jc 表更稳。)

**新版 Jc（字段名 → {req, res}）** 把手动功率/周期细分为 1/2/3/4/6 档
（`manual_power_1..6` / `manual_period_1..6`），结构更规整，建议以 Jc 为准。
完整两张表见 `app-service.js` 中 `Zc=` 和 `Jc=` 的定义（偏移 ~283450 / ~285612）。

## 6. 状态读取（心跳，接口 3 / iu）

响应解析（len 10）：

| 字段 | 字节位 | 含义 |
|------|--------|------|
| software_version | res[3] | 软件版本（决定用 Zc 还是 Jc）|
| current_mode | res[4] | 当前模式 |
| current_power | res[5] | 当前功率/强度 |
| current_temp | res[6] | 当前温度 |
| current_period | res[7] | 当前周期 |
| status / last_online | 由 errCode 推导 | 在线/离线 |

`res[2]` 是设备错误码（`Qc` 错误码表），0 表示正常。
读全部配置用接口 2（nu），一次返回全字段，适合初始化时拉完整状态。

---

## 7. MQTT 云端通道（远程控制，非本地）

- Broker：阿里云消息队列 MQTT，`wxs://post-cn-<实例>.mqtt.aliyuncs.com:443/mqtt`（WebSocket-Secure）。
- 认证：阿里云 **Signature 模式**。App 内置一对阿里云 AccessKey（Id+Secret）、
  MQTT 实例 ID、GroupID `GID_zaolang_user`，**全体用户共用同一套**。
  ClientId 每次随机（`GID_zaolang_user@@@<uuid>`），password = HmacSHA1(ClientId, Secret) 的 Base64。
  这些明文常量就在 `app-service.js` 里（`Ph/Nh/Bh` 等变量，偏移约 283000），你本地那份就能取到，我不在这里复制密钥串。
- 主题（`{device_id}` 为你的设备 ID）：
  - 下发：`device_cmd/req_update_config/{device_id}`、`device_cmd/req_config/{device_id}`、
    `device_cmd/req_config_time/{device_id}`、`device_cmd/req_ota_update/{device_id}`、
    `device_cmd/req_updata_config_v2/{device_id}`
  - 心跳：`device_heartbeat/req_update/{device_id}`
  - 响应：把上面 `req_` 换成 `res_`，设备发到该主题。
- payload 是二进制（Uint8Array），就是 §2 的帧。

**风险**：用的是厂家塞在 App 里的全局密钥连它的生产 MQTT，非官方用法；
厂家一旦轮换密钥 / 换实例 / 加服务端校验，这条路立即失效。device_id 还得从云端设备列表拿。

## 8. BLE 本地通道（推荐）

透传串口模块（源码里同时出现两组，以第一组为主）：

- 主：Service `55535343-FE7D-4AE5-8FA9-9FAFD205E455`
  - 写特征 `49535343-8841-43F4-A8D4-ECBE34729BB3`
  - 通知特征 `49535343-1E4D-4BD9-BA61-23C647249616`
  - （这是 Microchip / ISSC BM70/RN487x 系列透传 UART 的标准 UUID）
- 备：Service `0000FFF0-...`，写 `FFF1`、`FFF2`。

用法：连上 GATT → 订阅通知特征 → 往写特征发 §2 的帧 → 从通知特征收响应帧。
**不需要 device_id、不需要云、不需要密钥。** 配网帧（接口 4）结构是
`[...SSID字节, 0x0D, 0x0A, ...密码字节]`，但本地控制用不到配网，直接发控制帧即可。

> 待物理验证：泵联网运行时 BLE 是否持续广播/可连，还是只在配网时开。
> 安信可模组通常可同时跑 Wi-Fi+BLE，但需实测确认。若 BLE 常驻，则本地 BLE 控制完全可行。

---

## 9. Home Assistant 接入方案

两条路，建议优先本地 BLE：

**方案 A（本地 BLE，推荐，网络安全最优）**
- 用 HA 的 `bluetooth` + 一个自定义集成（基于 `bleak`）：扫到泵 → 连 UART → 收发帧。
- 实体建议：`fan`（开关 + 百分比映射到 manual_power）、`number`（周期）、`select`（手动/自动、正反转）。
- 优点：不联网、不依赖厂家云、无密钥失效风险。
- 约束：HA 主机要在泵的蓝牙范围内，或用蓝牙代理（ESPHome BLE proxy）覆盖。

**方案 B（云端 MQTT，功能最全但脆）**
- 自定义集成用 App 内置阿里云密钥连同一 broker，按 device_id 收发。
- 优点：远程、无距离限制。
- 缺点：依赖公网和厂家不换密钥；device_id 需先从云端设备列表取得。

**共同的实现要点**：帧构造 `[250, 接口号, 数据, sum%255]`；
优先按 `software_version` 判断用 Zc 还是 Jc 表；状态轮询用心跳接口（3）。

## 10. 仍需确认 / 下一步

1. BLE 是否联网时常驻（决定方案 A 是否可行）——需拿设备实测扫描。
2. manual_power / manual_period 的取值范围和单位（档位 0–x？周期秒数？）——
   读一次全配置或抓一次 App 操作即可标定。
3. current_mode / manual_mode 各数值对应的实际造浪模式名称。
4. 你的泵 software_version，确定用哪套字段表。
5. device_id 的实际形态（走方案 B 才需要）。

> 本文基于静态反编译，用于与你自己设备的互操作/本地控制；未对厂家服务做任何攻击性操作。
