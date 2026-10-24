# GTS / Zetlight / DualKey 交叉审计 — 2026-10-24

结论：**request changes**。记录 12 项问题：high 7、medium 5；critical/low/info 均为 0。
这不是十二项都在真机发生过，而是代码、模拟通信复现、配置检查所支持的风险清单。

审计对象包括 Claude 已有实现，也包括 Codex 本轮补救改动。A01 明确涉及本轮新增的潮汐恢复路径，不能归为仅仅是前一位执行者的问题。

## 范围与证据边界

输入检查点：GTS `db2bd6b`、Zetlight `eec96fa`、DualKey `f56b4c4`。
覆盖两套集成的协议、协调器、实体、配置/服务入口，11 份 Zetlight 蓝图、DualKey 固件和两份蓝图，及对应测试/交接。没有重新抓取厂商协议，也没有为审计执行新的真实停泵、断电、闪电、日程写入或固件上传。

实际运行：GTS 28 项测试、Zetlight 28 项协议测试、风暴 7 个转换场景、状态灯 6 项测试。另用真实类的 AST 配模拟通信执行 7 个探针函数，得到 8 条反例输出；DualKey 的旧延时回调用配置驱动的时序模型构造反例。模拟结果不等于真机验收。

本次审计结束前未改产品代码，也没有推送、打标签或创建 Release。此前已经授权的发布仍有效；A01 命中拟发布恢复路径，因此发布暂缓，不能把短测成功等同于故障和并发边界已通过。

## Review progress

- [x] Review target identified：三套当前实现及本轮补救提交。
- [x] Intent gathered：原生喂食、回水插座断电、自动恢复、防误触、可配置状态灯。
- [x] All changed files reviewed：补救提交的代码、蓝图、测试与交接已复读，并向原有调用链追踪。
- [x] Security swept：固件更新、设备事件授权、控制器来源隔离。
- [x] Performance swept：事件订阅范围、轮询和逐帧发送；未进行负载基准。
- [x] Consistency swept：模式、曲线、恢复状态、入口与 UI 语义。
- [x] Blast radius traced：实体 → 协调器 → 传输 → 蓝图 → 插座/设备恢复。
- [x] Findings logged：每项均有严重度、位置、影响和建议；落实到各仓库现有账本。
- [x] Overall summary written：下列问题与修复顺序；没有把未测项写成通过。

## A01 [high] GTS 多步启动不能保证后发停泵生效，末步失败会遗留手动大流量

**Category:** Bug。**位置：** [fan.py:177](/Users/rudyl/Developer/ha-gts-wavepump/custom_components/gts_wavepump/fan.py:177)，以及 [逐帧锁:180](/Users/rudyl/Developer/ha-gts-wavepump/custom_components/gts_wavepump/__init__.py:180)。账本 GTS-R06。

设备锁只包住单帧，不包完整“手动 → 波形 → 功率 → 潮汐”。模拟先启动、随后停泵，得到 `manual → off → waveform → power80 → tide`：后发的停泵命令被尚未结束的启动覆盖。另一个探针在最后的 tide 写入失败时，前面的手动模式/功率 80 已写入，函数只抛异常，没有恢复或不确定状态处理。

**建议：** 在设备级串行化完整操作，避免波形选择、开关和曲线操作彼此穿插；定义停止指令的优先级。逐步记录已确认状态，处理中途失败/取消并读回核对，不能仅在第一帧失败时测试异常。验收应包含每个写入位置失败、启动期间停泵、任务取消，以及停止完成后不被旧操作重新启动。

## A02 [high] GTS 潮汐写一半失败，重试可能把一半曲线再缩小一次

**Category:** Bug / data integrity。**位置：** [number.py:209](/Users/rudyl/Developer/ha-gts-wavepump/custom_components/gts_wavepump/number.py:209)，[逐段写入:234](/Users/rudyl/Developer/ha-gts-wavepump/custom_components/gts_wavepump/__init__.py:234)。账本 GTS-R07。

从 100% 调到 50% 时，24 段不是整体提交。模拟前 12 段成功、随后蓝牙失败；UI 仍为 100%。下一次轮询读到半份新曲线后重试，因为 `native_value >= 100`，代码会用这份半成品覆盖原基线。原值全为 80，目标应全为 40；复现结果是前 12 段为 20、后 12 段为 40，原曲线也失去了恢复依据。

**建议：** 写入前保存不可变、可恢复的完整基线和待完成目标；失败后不得从半写入结果重新捕获基线。操作串行化、逐段核对，并明确恢复/继续策略；只有完整确认后才提交新的比例。覆盖第 1/中间/最后一段失败及跨重启恢复。

## A03 [medium] GTS 把任意通知当成写成功

**Category:** Bug。**位置：** [通知回调:176](/Users/rudyl/Developer/ha-gts-wavepump/custom_components/gts_wavepump/__init__.py:176)，[写接口:253](/Users/rudyl/Developer/ha-gts-wavepump/custom_components/gts_wavepump/__init__.py:253)。账本 GTS-R08。

通知回调会用任何收到的字节完成当前 Future，而写接口没有检查返回内容。模拟返回 `not-a-valid-ack`，`async_write_named` 仍成功返回。延迟的旧响应或无关通知也可能被当成当前写入的确认。心跳读取虽然之后会解析，写入侧却没有这道边界。

**建议：** 按已有抓包合同校验帧格式、接口/字段及设备错误；只匹配当前请求。若设备协议不提供足够关联字段，应读回验证并把无法确认的结果报告为不确定，不能虚构 ACK。加入错接口、坏校验、旧响应、错误码和超时测试。

## A04 [high] Zetlight 喂食计时器不跨重启，整缸回水恢复依赖可能丢失

**Category:** Bug / recovery。**位置：** [初始化:385](/Users/rudyl/Developer/ha-zetlight-m5/custom_components/zetlight_led/__init__.py:385)，[计时器:630](/Users/rudyl/Developer/ha-zetlight-m5/custom_components/zetlight_led/__init__.py:630)，[卸载:914](/Users/rudyl/Developer/ha-zetlight-m5/custom_components/zetlight_led/__init__.py:914)。账本 F18。

`feeding_on` 和截止回调只在内存里。新协调器固定为 false、没有待恢复截止时间。喂食时若已断开回水插座，HA 重启后既没有持久计时任务，也没有保证补执行的整缸恢复步骤；不能依靠启动顺序偶然产生一次 off 状态事件。集成卸载还未取消旧的计时回调，重载后旧任务可能访问已关闭客户端。

**建议：** 持久化喂食截止时间和恢复义务；启动时先对账，再根据明确的喂食/维护策略恢复。卸载时取消本实例回调，但保留可续接义务。测试整个 HA 重启、仅集成重载、过期和未到期、设备暂不可达，并验证回水插座最终状态。

## A05 [high] Zetlight 调光期间换预设，恢复 100% 会覆盖回旧曲线

**Category:** Bug / data integrity。**位置：** [写日程:710](/Users/rudyl/Developer/ha-zetlight-m5/custom_components/zetlight_led/__init__.py:710)，[调光基线:735](/Users/rudyl/Developer/ha-zetlight-m5/custom_components/zetlight_led/__init__.py:735)。账本 F19。

命名预设和 set_schedule 直接写设备，不更新或结束 `_acclimation_base`。复现：旧基线 80、调光 50%，写入新预设 30，再调回 100%，实际又写入旧曲线 80。新预设被静默覆盖；UI 的当前预设也不再代表设备内容。

**建议：** 定义“调光期间更换基准日程”的单一合同：先恢复再换，或原子地更换基线并按当前比例应用。不能保留旧基线同时接受新曲线。失败时保留两者来源，读回确认后再提交；测试预设入口和服务入口。

## A06 [medium] Zetlight 特效、喂食、观赏和手动关灯缺少共同的控制优先级

**Category:** Bug / consistency。**位置：** [特效清理:551](/Users/rudyl/Developer/ha-zetlight-m5/custom_components/zetlight_led/__init__.py:551)，[云彩清理:626](/Users/rudyl/Developer/ha-zetlight-m5/custom_components/zetlight_led/__init__.py:626)，[观赏模式:687](/Users/rudyl/Developer/ha-zetlight-m5/custom_components/zetlight_led/__init__.py:687)。账本 F20。

特效锁只互斥闪电/云彩。清理无条件发 START 恢复日程，不检查期间是否进入了喂食、观赏或明确关灯。探针中喂食开关仍为 true，但执行真实的特效清理恢复例程后，灯已经回到日程 80，而非喂食亮度 20。喂食和观赏也能同时显示开启，其中一个关闭又会覆盖另一个。

**建议：** 定义用户关灯、维护、喂食、观赏、短特效、日程的优先级和当前所有者；效果结束只在自己仍拥有控制权时交还，恢复到当前有效意图，不能无条件 START。测试过程中切换模式和关灯。不要用一个大锁让紧急关灯排队等待完整特效结束。

## A07 [high] 公共喂食/维护蓝图会因造浪泵恢复错误而跳过插座上电

**Category:** Bug / recovery。**位置：** [whole_tank_feed.yaml:73](/Users/rudyl/Developer/ha-zetlight-m5/blueprints/automation/zetlight_led/whole_tank_feed.yaml:73)，[maintenance:83](/Users/rudyl/Developer/ha-zetlight-m5/blueprints/automation/zetlight_led/whole_tank_maintenance.yaml:83)。账本 F21。

结束步骤先执行蓝牙泵的 turn_on，之后才恢复额外插座。如果泵实体仍加载但 BLE 写入抛异常，默认脚本会停在这一行，回水泵/加热插座不会收到恢复命令。这一默认中止语义可核实于 [HA 官方文档](https://www.home-assistant.io/docs/automation/building-blocks/#continuing-when-a-step-fails)。单纯“不存在/不可用实体”可能被 HA 跳过，不能把这种情形和实际服务异常混为一谈。

**建议：** 独立保存并履行每个设备的恢复义务；单个设备错误不能阻止其他必要恢复。错误仍须可见，不能全部吞掉。现场自定义喂食自动化本轮已经把回水插座放到 BLE 恢复前，但公共蓝图仍需修复，维护恢复还需遵守用户退出维护的决定。

## A08 [high] DualKey OTA 没有认证，配合 HA 动作权限形成更大的控制入口

**Category:** Security。**位置：** [reef-dualkey.yaml:43](/Volumes/home-1/Coding/M5Stack/reef-dualkey.yaml:43)。账本 DK-R06。

当前配置为裸 `api:` 和裸 ESPHome OTA 平台，没有 API 密钥、OTA 加密或 OTA 密码。用户此前明确接受了为这台设备开启 HA 动作权限，但没有认证的固件上传是另一条控制入口：能到达 OTA 端口的网络主体可以替换固件，随后不必遵守原本的本地按键锁。没有进行任何攻击上传。该默认行为及新版本的加密方案见 [ESPHome 官方 OTA 文档](https://esphome.io/components/ota/esphome/#encryption)。

**建议：** 使用设备独有的 API 密钥和加密 OTA，密钥只放 secrets；按当前版本的迁移流程与 HA 配对一起更新，不能只改 YAML 就宣称真机已安全。保留 USB 恢复路径。可达性和 VLAN 限制可缩小暴露面，但不能替代固件更新认证。

## A09 [high] DualKey 额外断电设备只在再次按键时恢复，不随模式自动到期恢复

**Category:** Bug / flow completeness。**位置：** [key_actions.yaml:96](/Volumes/home-1/Coding/M5Stack/blueprints/automation/reef_dualkey/key_actions.yaml:96)，[恢复步骤:142](/Volumes/home-1/Coding/M5Stack/blueprints/automation/reef_dualkey/key_actions.yaml:142)。账本 DK-R05。

蓝图仅监听六种按键事件。按键启动喂食时它会关掉 extras，但如果喂食开关被灯自身的计时器关闭，没有对应的状态触发器，extras 会继续断电。另一份自动化或面板关闭模式也一样。文案声称“跟模式开关状态联动”，实现却不是。当前现场 extras 留空，由已有喂食自动化负责插座，因此没有启用这条有缺口的恢复路径。

**建议：** 按键只改变模式意图；由独立的模式状态/截止时间流程统一管理插座，覆盖定时退出、手动退出和重启。避免与其他蓝图重复管理同一插座；恢复时还须考虑维护模式是否仍拥有停电意图。

## A10 [medium] DualKey 蓝图没有按设备筛选手势，多控制器会串控

**Category:** Bug / isolation。**位置：** [key_actions.yaml:96](/Volumes/home-1/Coding/M5Stack/blueprints/automation/reef_dualkey/key_actions.yaml:96)。账本 DK-R07。

所有实例只匹配全局 `esphome.reef_key*` 事件类型，没有设备输入或 `device_id` 过滤。两台控制器或两套鱼缸自动化并存时，一台按键能触发所有实例。现场收到的真实事件已有 device_id，具备隔离依据；无需按名字猜目标。

**建议：** 显式选择控制器设备，并匹配事件的真实 device_id。测试目标设备、其他设备、缺少设备标识的事件；后两种不能控制本实例。

## A11 [medium] DualKey 松键没有取消旧的组合键延时，存在提前解锁的时间序列

**Category:** Bug / safety interaction。**位置：** [reef-dualkey.yaml:270](/Volumes/home-1/Coding/M5Stack/reef-dualkey.yaml:270)，[on_release:292](/Volumes/home-1/Coding/M5Stack/reef-dualkey.yaml:292)。账本 DK-R08。

on_press 延时 1.5 秒后只看“两键此刻是否都按下”，on_release 没取消旧的 hold continuation；另一条 0.4 秒清除 guard 的延时也没有代次关联。按 0.2 秒松开，在第 1.4 秒重新同时按住，旧回调会在第 1.5 秒看到两键按下并切锁，此次连续按住实际上只有 0.1 秒。配置驱动的时序模型已构造该反例；本机 ESPHome DelayAction 实现也允许并行未结束延时。尚未在真机刻意执行该异常时序。

**建议：** 组合键用可取消/带代次的单一保持任务；任一键松开立即取消该次保持。旧的 release 回调不得清除新一轮 combo guard。覆盖短按重试、交错松开、连做两次、重上锁期间的单键动作，最后再真机验收。

## A12 [medium] Zetlight 读选项失败后仍写零，会意外关闭其他功能

**Category:** Bug / failure handling。**位置：** [__init__.py:280](/Users/rudyl/Developer/ha-zetlight-m5/custom_components/zetlight_led/__init__.py:280)，[auto-cloud:294](/Users/rudyl/Developer/ha-zetlight-m5/custom_components/zetlight_led/__init__.py:294)。账本 F22。

设置珊瑚驯化前本应保留 auto-cloud 和 phase；读失败却把它们设为 0 再发送。探针强制选项读取失败，仍得到 `[0, 0, 1]` 写入帧。反向设置 auto-cloud 时也会默认关闭 coral。网络瞬断会因此变成持久功能改变，而不只是一次操作失败。

**建议：** 不能把未知状态当成关闭。获取有效的新快照后再做受锁保护的读改写；读取失败时拒绝该修改并给出明确错误。覆盖读取失败、并发改不同字段和设备返回损坏选项的情况。

## 进一步优化：提议，不混入当前抢修

1. **先把恢复可观察化。** 面板区分“已发命令、设备已确认、状态未知、待恢复”，提供明确的设备目标和重试入口。灯的开关/亮度有乐观值，不能用它推断水泵或实际光输出已验收。
2. **测试从协议字节扩展到完整旅程。** 已有协议测试有价值，但应覆盖 HA 重载/重启、并发停止、逐步写失败、双控制器和模式交接。验证真实设备前先用合成目标运行自动化，避免把鱼缸当故障注入环境。
3. **缩小状态灯订阅范围。** 本轮新增模板在 `status_led.yaml:129` 监听全屋 state_changed，再在条件中过滤。对一台控制器不构成已证实的性能问题；多实例/高事件量时会增加无关模板计算。可在可选助手配置确定后只订阅相关实体，保留启动/重连重算，并测量事件量再决定优化力度。
4. **写日程要有明确目标。** 当前 set_schedule 服务会遍历所有已加载灯。建议增加明确的设备/实体目标，群控由用户显式选择；同时说明预设/调光基线如何处理，避免改一盏影响所有灯。

## 必须保持开放的验收

先前真实观察已证明：原生喂食进入 feed，后来恢复运行潮汐；DualKey 真实解锁、长按进入 HA 及约 30 秒自动上锁。它们不覆盖本报告的故障/并发条件。完整喂食含插座循环、长时连接稳定性、异常组合键、真正的风暴、状态灯实际告警、不同泵固件/型号，均未因这些短测自动通过。

## 执行顺序与发布

第一组：GTS-R06/A01（直接挡住 0.6.2）、F18/A04、F21/A07、DK-R06/A08，先处理停止/恢复/固件授权边界。
第二组：GTS-R07/A02、F19/A05，保护两套原始曲线；GTS-R08/A03 处理设备确认。
第三组：F20/A06、DK-R05/A09、DK-R07/A10、DK-R08/A11、F22/A12，再处理模式和交互完整性。

这只是实施顺序提议，不是本轮只读审计自动获得全部实施授权。推送/发布授权已于本轮取得，不需要重新索取；但不能绕过已知发布阻断项。建议强推理模型先修阻断与恢复，再以普通模型执行核准内容的机械发布检查。

## 可复查的探针记录

保存的是只读诊断源码文本及实际输出，不是生产修复或新增已通过的产品测试：

- [真实类模拟通信探针源码](2026-10-24-evidence/probes-source.txt) / [实际输出](2026-10-24-evidence/probes-results.txt)。原运行命令：`python3 /private/tmp/reef-recovery-20261024/audit_probes.py`。
- [组合键时序模型源码](2026-10-24-evidence/combo-source.txt) / [实际输出](2026-10-24-evidence/combo-results.txt)。原运行命令：ESPHome Python 环境执行该脚本。

源码文本保留本机路径，以便当前项目接续；重放时须将文本复制到临时 `.py` 文件，并确认对应仓库检查点。它们不连接真实设备，也不导入完整 HA 运行时。修复阶段应将反例转成仓库正式测试，再补 HA/设备验收。
