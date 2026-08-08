# macOS 外接键鼠 + 音频同时失灵排查手册

> 背景来源：Codex 会话 `019fb7da-ad7c-7742-acfc-3aa1165bf27f`（2026-07-31）
> 会话文件：`/Users/ark/.codex/sessions/2026/07/31/rollout-2026-07-31T19-06-29-019fb7da-ad7c-7742-acfc-3aa1165bf27f.jsonl`
> 目的：该场景复现时，按本手册直接抓现场、定位根因。

## 1. 设备拓扑（已确认）

- 主机：MacBook Pro，macOS 25.5.0（Darwin 25.5.0，arm64，T6020），`fangzhoudeMacBook-Pro.local`
- 外设全部挂在同一颗 **GenesysLogic USB Hub** 链路下：
  - `USB3.1 Hub`（GenesysLogic，idVendor 1507 / idProduct 1574）
  - `USB2.1 Hub`（GenesysLogic，idVendor 1507 / idProduct 1552）← 键鼠所在
  - **BAN60 Pro 键盘**（GigaDevice，idVendor 1101 / 0x44d，idProduct 1234 / 0x4d2，序列号 `66DB627C0B4D`）
  - **Logitech USB Receiver**（鼠标，idVendor 1133 / 0x46d，idProduct 50504 / 0xc548）
  - ASIX `AX88179A` USB 网卡（idVendor 2965 / idProduct 6032）
  - 另有 2 个 `USB 2.0 Hub`（idVendor 6720 / 0x1a40）
- **Bose mini 音箱**：通过 **3.5 mm 模拟线直插 MacBook 耳机口**（不是 USB、不是蓝牙；系统里另有 BoseQuietControl30 蓝牙耳机记录，勿混淆）
- 显示器：**GX321UR**（带 USB Hub / KVM 的显示器）

## 2. 故障现象（已发生两次）

1. 外接键鼠先后失灵：先鼠标指针消失，键盘稍后也失灵；几分钟后鼠标指针回到 GX321UR 屏幕中央，随后键鼠恢复。
2. 第二次故障同时出现：直连 3.5 mm 的 Bose mini 音箱也无声（视频仍在播放）。

## 3. 已确认的事实与证据

- 设备本身无故障：两套外设 HID 均被 macOS 正常枚举，无 USB/HID 报错、无驱动问题、无线缆松脱。
- **故障现场（23:09）**：`hidutil list` 中 BAN60 Pro 与 USB Receiver **同时消失** → 确实断线，不是输入服务卡住。
- **恢复后（23:15）关键对比**（重新枚举的铁证）：

| 指标 | 故障前/正常（11:10） | 恢复后（23:15） |
|---|---|---|
| BAN60 Pro USB sessionID | 32972065125397 | 33294512341574 |
| BAN60 Pro HID RegistryID | 0x10013ec38 | 0x1001424eb |
| BAN60 Pro locationID | 0x1110000 | 0x1130000 |
| BAN60 Pro USB Address | 6 | 5 |
| Receiver USB sessionID | 30909839377231 | 33323790390566 |

  → 键鼠在同一个 USB2.1 Hub 下被系统**重新枚举**（端口重新分配），恢复时指针跳回 GX321UR 中央说明显示器会话同时发生过重配置。
- 已排除：电池（全有线）、单设备故障、驱动、输入服务单独故障。

## 4. 定位分支（下次复现时的判定逻辑）

| 故障时的现象 | 含义 |
|---|---|
| 内建键盘/触控板正常；外接键鼠失效 | 问题基本锁定在 **扩展坞/USB Hub、Hub 上游 USB-C 线、或显示器 KVM/USB 上游链路** |
| 内建键盘/触控板**也**失效；Bose 同时无声 | 超出扩展坞：更像 **macOS 图形/输入会话、主机 I/O 或电源管理异常**（直连音频无声支持此方向） |
| 内建设备正常，但 Bose 仍无声 | USB 故障和音频输出切换/静音可能是**两件事**，需分别查音频路由 |

优先级从高到低的怀疑对象：
1. 扩展坞/显示器 USB Hub 短暂掉线、供电不足或固件卡住
2. Hub 与 Mac 间 USB-C/雷电线接触、兼容性或带宽问题
3. GX321UR 的 USB Hub/KVM 或输入源切换、节能唤醒导致 USB 上游重连
4. macOS 显示器重配置 / HID 输入服务短暂异常（可解释直连音频同时无声）

## 5. 下次复现时的行动清单

**用户先做（保持现场！）：**
- 不要拔插扩展坞/键鼠/音频线，不要重启
- 立刻用内建触控板移动/点击，按一下内建键盘 Caps Lock，观察是否有效
- 观察并口头告知：①视频画面是否仍在播放（只是无声？）②GX321UR 是否闪黑/刷新/分辨率变化 ③故障大约发生时间

**排查者执行（按序抓现场）：**
```bash
# 0) 时间基准
date '+%Y-%m-%d %H:%M:%S %z'

# 1) HID 列表——外设是否还在（消失=断线中）
hidutil list 2>/dev/null | rg 'BAN60 Pro|USB Receiver|Apple Internal Keyboard / Trackpad'

# 2) USB 拓扑与 sessionID / locationID / USB Address（对比 §3 基线）
ioreg -p IOUSB -l -w0 2>/dev/null | rg -A 24 'BAN60 Pro@|USB Receiver@' | rg 'class IOUSBHostDevice|sessionID|USB Product Name|locationID|USB Address'

# 3) USB 全量设备（观察是否有新设备/缺失设备，如 'USB2.0 Device' Generic）
ioreg -p IOUSB -l -w0 2>/dev/null | rg 'USB Product Name|USB Vendor Name'

# 4) 近期 USB/HID/显示器相关系统日志
log show --style compact --last 30m --predicate '(process == "kernel" OR process == "usbd" OR subsystem CONTAINS[c] "USB" OR eventMessage CONTAINS[c] "USB")' 2>/dev/null | tail -n 200

# 5) 音频：3.5mm Headset 设备是否还在、当前输出
system_profiler SPAudioDataType 2>/dev/null | rg -i -C 3 'Output|Default|Headset|Speaker'

# 6) 显示器状态（重连/分辨率变化记录）
system_profiler SPDisplaysDataType 2>/dev/null | rg -C 4 'GX321UR|Resolution|Connection Type'
```

**判定：** 把 1/2 的输出与 §3 基线表对比；结合用户口述的内建设备/画面/屏幕现象，套用 §4 分支。

## 6. 基线值速查（正常态）

- BAN60 Pro：sessionID `32972065125397`，locationID `0x1110000`，USB Address 6，HID RegistryID `0x10013ec38`
- USB Receiver：sessionID `30909839377231`，locationID `0x1120000`，USB Address 3
- 两者均在 `USB2.1 Hub`（GenesysLogic）下；USB 树上出现 `USB2.0 Device`/`Generic` 或 BAN60 的 locationID 变为 `0x1130000` 即说明发生过重枚举

## 7. 遗留问题（未能验证）

- 故障发生时内建设备是否可用：未验证（上次恢复太快）。这是区分"扩展坞问题"与"macOS 会话/电源管理问题"的最关键一步，下次务必优先测。
- Bose 无声是否与键鼠失灵同源：未能从已恢复状态追溯，需下次现场抓 CoreAudio。
