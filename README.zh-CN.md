# 狗头鲨 GTS 造浪泵 — Home Assistant（本地蓝牙）

[English](README.md) | **简体中文**

一个用于**狗头鲨（Goutousha）GTS 造浪泵**（**L20 和 L40**）的 Home Assistant 自定义集成，
**完全走本地蓝牙（BLE）控制**。它是 GTS Aqua App 的**本地化、零云端替代**：不连厂家云、
不走阿里云 MQTT、不需要任何密钥。两个型号用同一套蓝牙协议，会被自动发现
（广播名 `GTS_WAVE20_*` / `GTS_WAVE40_*`），并在设备页显示具体型号。

泵在 Wi-Fi 侧不开放任何本地网络服务（Wi-Fi 只用于连厂家的阿里云 MQTT），所以本地控制只能走
蓝牙。泵通电在线运行时，蓝牙会持续广播且可连接。

> 协议来源：从官方 App 反编译分析得到，记录在
> [`docs/gts-l20-protocol.md`](docs/gts-l20-protocol.md)。本集成不与厂家云发生任何通信。

## 前置条件

- Home Assistant 已配置 **Bluetooth（蓝牙）**集成。
- HA 主机上有**蓝牙适配器**，**或**一个在鱼缸蓝牙范围内的 **ESP32 蓝牙代理**（ESPHome
  `bluetooth_proxy`）。只有 ESP32 固件（如果你用代理）才需要编译一次；集成本身是纯 Python，
  不需要编译。
- `bleak-retry-connector`（已在 manifest 声明，HA 会自动安装）。

## 安装

**方式一：HACS（推荐）**
HACS → 集成 → 右上三点 → 自定义存储库 → 添加
`https://github.com/rudyll/ha-gts-wavepump`（类别选 Integration）→ 安装 → 重启 HA。

**方式二：手动**
把 `custom_components/gts_wavepump/` 整个目录拷到 HA 的 `config/custom_components/`，重启 HA。

重启后进 **设置 → 设备与服务**：泵会被蓝牙自动发现（广播名 `GTS_WAVE20_<序列号>`，
例如 `GTS_WAVE20_21000580`），确认添加即可；也可以 **+ 添加集成 → GTS Wave Pump** 手动加。
HA 是中文时，实体名、状态、配网流程、服务都会显示中文。

## 实体一览

| 实体 | 控制 / 读取 | 对应字段 |
| --- | --- | --- |
| `fan` 风扇（功率） | 开/关 + 强度百分比 | 当前档 `manual_power` |
| `select` 运行模式 | 手动 / 潮汐 | `manual_or_auto` |
| `select` 波形 | 恒定/脉动/正弦/乱流/涌浪 | `manual_mode` |
| `select` 主从机 | 主机 / 从机（多泵联动） | `master_or_slave` |
| `number` 周期 | 秒 | 当前档 `manual_period` |
| `number` 潮汐强度 | 覆盖百分比：整体缩放潮汐曲线 | `auto_p` × 系数 |
| `number` 喂食时间 | 分钟（即时喂食时长） | `feed_time` |
| `number` 通信频道 | 频道号 | `communication_channel` |
| `button` 喂食 | 立即喂食 | `manual_mode` = 5 |
| `switch` 灯光 | 开 / 关 | `light_on`（2=开/1=关） |
| `switch` 定时组 1/2/3 | 开/关某个定时喂食组 | 喂食组启用位 |
| `sensor` 温度 | °C | 心跳 `current_temp` |
| `sensor` 水流模式 | 当前运行波形 | 心跳 `current_mode` |
| `sensor` 潮汐排程 | 24 段曲线（只读，在属性里） | `auto_m/p/t` |
| `sensor` 定时喂食 | 3 个定时组（只读，在属性里） | 喂食组 |
| `sensor` 信号强度 | 最近适配器/代理的蓝牙 RSSI | 蓝牙 |
| `sensor` 固件版本 | `software_version`（诊断） | 心跳 |

另有服务 `gts_wavepump.set_tidal_schedule`（目标选 fan 实体）：一次性写入整条潮汐曲线
（最多 24 段 `{mode, power, period}`），方便自动化重排一天的流态。

状态每 30 秒轮询：心跳（接口 3）给出模式/功率/温度/周期，读全配置（接口 2）填充各 select /
number / switch。协议字段表（`Zc`/`Jc`）按版本自适应（`software_version > 4` 用新版 `Jc` 表），
已在 software_version 17 的真机上验证。

说明：
- 调强度或切波形会**强制进入手动模式**（泵离开潮汐排程），和 App 里直接控制的行为一致。
- **开/关**用的是 App 的真命令：关=`manual_mode`=7（关机），开=恢复一个波形并带功率。
  `manual_mode`=5 是喂食（喂食按钮）。
- **潮汐曲线**在传感器里只读，可通过 `set_tidal_schedule` 服务批量写；没有逐段编辑的 UI
  （曲线可视化编辑请用 App，或用服务在自动化里改）。
- **潮汐强度**：按百分比从持久化的"基线"整体缩放 24 段曲线（零漂移，100% 精确还原）——
  用于**珊瑚驯化**（整缸流量按比例降低再逐日升回），**不改动每小时各自的波形和相对功率**。
  只在潮汐模式下生效。

## 工作原理

标准 ISSC/Microchip 透传串口 GATT：

- 服务 `55535343-FE7D-4AE5-8FA9-9FAFD205E455`
- 往 `49535343-8841-43F4-A8D4-ECBE34729BB3` 写帧
- 从 `49535343-1E4D-4BD9-BA61-23C647249616` 收通知响应

帧格式 `[250, 接口号, ...数据, 校验和]`，`校验和 = 前面所有字节之和 % 255`。建帧/解析都在
[`protocol.py`](custom_components/gts_wavepump/protocol.py)（与 HA 无关，有单元测试
[`tests/test_protocol.py`](tests/test_protocol.py)）。

> 注：真机的收发特征和 Microchip 惯例是反的；集成在连接时按 GATT 属性自动识别读/写特征。

## 尚未支持 / 待办

- **定时喂食**：3 个定时组在 HA 里可开/关；但**时间是只读**的（请在 App 里设）——每组时间的
  写入 id 是厂家热更新新增的功能，不在安装包 APK 里。
- **周期**的原始取值上下限未精确标定（用了较宽的范围）。
- **正反转**（`forward_or_reverse`）有意不暴露：L20 固件已取消反转功能，App 也不提供。

## 运行测试

```bash
python3 -m pytest tests/test_protocol.py -q
```

协议测试不依赖 Home Assistant。
