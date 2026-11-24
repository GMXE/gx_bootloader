> 当前发布入口（2026-11-23）：dist/gmxe_bootloader_v1-intdfu-2000ms.bin（PA11/PA12）及extdfu同名变体（PB14/PB15），两版2000ms。统一采用索引6和擦写等待修复，不再使用带fix后缀的调试镜像。用户确认intdfu应用擦除和下载完成；leave状态请求报错，应用启动/读回与extdfu实板测试待验收。历史记录中的“未下载”和“修复待复测”以此为准。
>
> 构建、烧录和优化指引：../libDaisy/docs/gmxe/BOOTLOADER.md。此前错误的官方派生源码和旧产物已移出使用路径，归档于工具目录DaisyBootloader/archive_gmxe_obsolete_20261123（禁止烧录）。
>
> 发布范围（2026-11-24）：`release.py` 只产出 bootloader（standard 2000ms + yola_voice 100ms）。产品、UI、自检及未来新产品固件由各自工程生成，不在本仓库 `dist/` 内。

# GMXE Bootloader v1：W9825G6KH-6配套实验版

2026-11-15，已交叉编译与镜像静态检查，未烧录、未实板验收。用于GMXE自研STM32H750IBT6板，不用于官方Daisy Seed。
应用工程为 `../gmxe project/YOLA_VOICE_gx`；配套库为 `../libDaisy`（GMXE profile）。

## 文件与地址

本仓库 `release.py` 只产出 bootloader，`dist/` 仅含下表四份 loader。自检、YOLA 产品/UI 及未来新产品固件由各自工程构建，不随本仓库发布。

| dist文件 | 用途 | 烧入地址 |
|---|---|---|
| gmxe_bootloader_v1.1-intdfu-2000ms.bin | standard，PA11 D− / PA12 D+，等待2000ms | 片内Flash 0x08000000 |
| gmxe_bootloader_v1.1-extdfu-2000ms.bin | standard，PB14 D− / PB15 D+，等待2000ms | 片内Flash 0x08000000 |
| yola_voice_int.bin | YOLA专用，PA11/PA12，等待100ms，产品串 YOLA Voice int | 片内Flash 0x08000000 |
| yola_voice_ex.bin | YOLA专用，PB14/PB15，等待100ms，产品串 YOLA Voice ex | 片内Flash 0x08000000 |

四份只能选择一份写入 0x08000000。应用/自检（如 SdramTest、YOLA 产品/UI）由各自项目生成，烧到 QSPI 0x90040000、在 0x24000000 执行；配套 elf/map 供 SWD 调试，manifest.json 及 SHA256SUMS 记录构建与校验值。
这不是整片合并image：先烧loader，再通过它烧应用；不能把应用bin烧到0x08000000。

## 烧录顺序

1. 用SWD，或芯片ROM DFU，把新loader写到0x08000000。ROM DFU入口由BOOT0/RESET决定；可先尝试板载PA11/PA12接口。自定义loader的extdfu配置不决定芯片ROM支持哪个USB口。这里没有自动执行烧录。
2. 恢复BOOT0正常启动，intdfu连接PA11/PA12常规USB；extdfu连接PB14/PB15外接USB。standard版复位后有2000ms下载窗口（yola_voice版为100ms）；无有效应用时持续等待。v1.1 起复位后读取 PG3(BOOT)，按住可阻止自动跳转（详见 yola_voice 小节）。PC7未配置USB时闪烁，USB配置后长亮；下载完成后leave复位状态仍待实板核对。
3. 在现有GMXE Flasher选择“固件升级”，手动选择自检工程产出的 `GMXE_SdramTest_BOOT_SRAM.bin`（本仓库不打包），确认目标为0x90040000。USB名称为“GMXE Bootloader v1 intdfu”或“GMXE Bootloader v1 extdfu”（yola_voice 为“YOLA Voice int/ex”），VID:PID仍为0483:DF11。Flasher原来的“必须BOOT_QSPI”文案不适用于这份BOOT_SRAM固件，其内置旧v6.4选项也不是本包的新loader。
4. 使用SWD附加对应自检elf，观察 `gmxe_sdram_report`：magic=0x47585344、phase=100、passed=1才表示本轮32MiB读写/保持测试完成。失败保留status/clock_hz/refresh_count/address/expected/actual；此自检没有显示屏或串口结果输出，也不启动音频。
5. 自检通过后，再复位进入下载窗口，把槽位替换为YOLA实验固件。产品/UI均构建通过，但TAC5242驱动和完整GMXE音频引脚映射尚未适配，不能据此承诺正常出声。下一步是音频BSP及实板整机回归。

使用dfu-util时，分别在已进入正确DFU的状态下执行（仅示例）：

```sh
dfu-util -a 0 -s 0x08000000:leave -D gmxe_bootloader_v1-extdfu-2000ms.bin
dfu-util -a 0 -s 0x90040000:leave -D GMXE_SdramTest_BOOT_SRAM.bin
```

PA11/PA12保留为独立常规USB线路；本次按官方编译选择分别提供intdfu与extdfu，各自只初始化选定的USB控制器，不新增双口/自动切换。PB14/PB15使用OTG_HS的片内PHY，以Full Speed运行，不是ULPI高速模式。

## 启动所有权与约束

loader只初始化System、QSPI IS25LP064A、USB DFU、PC7和PG3，不初始化SDRAM、codec、音频、SDMMC或USB Host。
QSPI采用PF8/PF9/PF7/PF6/PF10/PG6，与当前原理图相符。
下载后将QSPI槽位的前480KiB复制到AXI SRAM；写backup SRAM请求标志并执行系统复位；复位后的loader在外设初始化前验证向量、请求和复位来源，设置一次性ABI v1标志，再跳应用。
应用重新建立时钟/MPU，并独占W9825G6KH x16冷初始化；仍拒绝无此交接的SRAM程序、QSPI XIP和已开启FMC。backup SRAM最后64B（0x38800FC0起）保留给ABI，linker有重叠断言。该标志用于启动兼容性检查，不提供固件安全认证。

DFU写入限定QSPI 0x90040000–0x907FFFFF，前256KiB保留；仅支持BOOT_SRAM执行，应用bin必须≤480KiB，不能把8MiB传输空间当执行容量。未实现断电更新恢复或镜像签名；向量检查不能证明完整镜像有效。传输失败需重新完整下载，首次实板测试保留SWD恢复方式。

## 独立仓库构建前置（依赖）

本仓库仅含loader源码与文档，不包含可独立编译所需的同级依赖；Makefile保持 `LIBDAISY_DIR = ../libDaisy` 的工作区布局，不做改动。构建前需按以下同级目录放置（`git clone <repo> <sibling>`）：

| 同级目录 | 来源 | 构建loader所需 | 备注 |
|---|---|---|---|
| `../libDaisy` | `GMXE/gxseed`（私有，GMXE profile） | 是（`core/Makefile`、ST USB 源、`board/gmxe_boot.h`） | loader 必需 |
| `../DaisySP` | DaisySP 本地库 | 否 | 本仓库不构建；仅产品固件工程使用 |
| `../gmxe project/YOLA_VOICE_gx` | `GMXE/YOLA_VOICE_gxseed`（私有） | 否 | 本仓库不构建；产品固件在其项目内生成 |

仅编译loader：`make USB_MODE=extdfu`（或 `intdfu`）或 `make yola_voice_int` / `make yola_voice_ex`，前提是 `../libDaisy` 已就位。`release.py` 只需 `../libDaisy` 与 `arm-none-eabi-*` 工具链，不再需要 DaisySP 或产品工程。

## 构建及来源

从本目录执行 `python3 release.py`，只构建 GMXE 库与四份 loader（standard ext/int 2000ms、yola_voice int/ex 100ms）并打包到 `dist/`；不构建 DaisySP、自检或产品/UI 固件。需要 arm-none-eabi 工具链及同级 `../libDaisy`。
USB DFU实现源于本地DaisyBootloader `8b279a8` 的shared文件，保留原ST许可证头，使用工作区libDaisy的固定USB/HAL依赖；不修改原loader目录。
修正原DFU的读回地址/返回指针、写缓冲长度检查、QSPI写入边界及错误状态；不包含旧loader的SD卡/USB存储自动升级功能。
构建检查覆盖四份 loader 的 128KiB 容量、DTCM 栈/Thumb 向量、ext/int 对应 USB 选择、DFU 索引6回调，以及 loader 符号排除 SDRAM/codec 初始化；真实USB枚举、下载读回、断电复位仍待实板执行（SDRAM 全区测试在自检工程进行）。

## yola_voice 专用 100ms 配置

在原版 `standard`（2000ms，产品串 `GMXE Bootloader v1 ...`，保持不变的通用开发板 loader）之外，新增 YOLA Voice 产品专用 loader：下载窗口缩短为 100ms 以加快开机。原版镜像、文件名与产品串均保留。

| 产物 | USB | 产品串 | 烧入地址 |
|---|---|---|---|
| dist/yola_voice_int.bin | 内部 PA11/PA12（intdfu） | YOLA Voice int | 片内Flash 0x08000000 |
| dist/yola_voice_ex.bin | 外部 PB14/PB15（extdfu） | YOLA Voice ex | 片内Flash 0x08000000 |

构建（需 `../libDaisy` 就位）：

```sh
make PROFILE=yola_voice USB_MODE=intdfu   # 产物 build_yola_voice_int/yola_voice_int.bin
make PROFILE=yola_voice USB_MODE=extdfu   # 产物 build_yola_voice_ex/yola_voice_ex.bin
# 等价便利目标：
make yola_voice_int
make yola_voice_ex
```

行为：100ms 内无 USB 枚举/活动且存在有效应用时即自动跳转，加快开机；进入 DFU 需复位时按住 BOOT(PG3)（`boot_button_pressed` 阻止自动跳转）或应用下发 `INF_TIMEOUT`。`SKIP_TIMEOUT` 分支仍固定 100ms，与 yola_voice 默认超时相同。`release.py` 只构建这四份 loader（含 yola_voice 两份），并按 ext/int 校验各自的 `USBInit_HS/FS` 选择；产品固件不在此仓库生成。
注：早期 v1 文档称「PG3 不作保持键」；当前 v1.1 代码在复位后读取 PG3(BOOT)，按住会阻止自动跳转，以本节为准。

## 本地烧录目录分发（历史，2026-11-15）

当前 `release.py` 只产出 bootloader 到本仓库 `dist/`；下方旧分发目录仅存档。历史目录：`/Users/wuenny/工具文件/Daisy-hardware/DaisyBootloader/dist/`，文件名 `gmxe_bootloader_v1-intdfu-2000ms.bin` / `gmxe_bootloader_v1-extdfu-2000ms.bin`。
两份只能选择一份写到0x08000000。两版使用相同SDRAM交接及相同应用bin。
LED源码位于 `../gmxe project/GMXE_BoardSmokeTest`；不调用DaisySeed::Init，不初始化SDRAM/codec。

## 本轮审核边界

用户最终要求：不新增USB功能，保留官方intdfu/extdfu编译选择；本轮未修改SDRAM驱动参数、应用、库或GMXE-Flasher。
本轮源码改动限于双变体可重复构建、固定2000ms参数、设备名称辨识和打包校验。

SDRAM审核：8192行×512列×4bank×16bit=32MiB，bank1/x16/13行9列/39条FMC GPIO；PLL2R/2仅接受90–100MHz，100MHz刷新计数761。驱动参数和GPIO交接仍是候选，必须实板测量与全区测试。
loader不初始化FMC，复制QSPI应用到AXI SRAM并复位；复位后启动ABI确认交接，应用重新配置时钟/MPU再初始化W9825G6KH。配套库/应用不能用旧官方loader替代。这个交接是现有GMXE冷启动驱动的要求，与USB版本无关。

这两份仍基于现有GMXE冷启动loader，不是官方全功能loader仅替换SDRAM参数：尚不含官方SD卡/USB存储升级与BOOT_QSPI执行。此次没有恢复这些功能，也不把它们宣称为硬件适配必需删除。若今后恢复，需单独检查板上引脚和启动所有权，不影响当前BOOT_SRAM bring-up。
原官方bin与参考源码不修改。真实旧板“两口可下载”的实测现象未解释，不以本次编译选择检查冒充实板验证。


## 2026-11-23 DFU 索引6修复

启用配套 gxseed 的 USBD_SUPPORT_USER_STRING_DESC，并重编库及 loader。DFU interface 请求的是索引6，由类驱动 USBD_DFU_GetUsrStringDesc 返回媒体布局；只修改索引5不足以修复。release.py 现在检查最终 ELF 必须包含该回调。双版本保持2000ms、原ABI及应用独占SDRAM冷初始化。库、双loader、YOLA产品/UI、自检构建通过，USB下载待用户实板复测。


## 2026-11-23 QSPI擦写等待修正

实板已能读取DFU索引6，但应用下载擦除阶段报ERASE_PAGE错误。代码确认64KiB请求由gxseed分16个4KiB擦除，200ms应答不能覆盖其最坏完成时间；恢复8000ms擦除等待，编程等待改20ms。此次保留异步擦写及错误传播、ABI和SDRAM配置。双loader和配套应用构建检查通过；是否解决实板错误待复测。


## v1.1（2026-11-24）

跳转沿用官方 boot_info JUMP + 软件复位 + 复位入口设置 VTOR/MSP 后跳转顺序；kBootRequest 是本次下载交接的准入令牌，用于排除ROM DFU后残留的旧backup SRAM/AXI SRAM状态。保持2000ms、DFU布局、QSPI擦写等待和32MiB x16配置。USB枚举期间不因2秒超时抢先跳应用；PG3不作为loader保持键。


## 2026-11-24 下载后应用交接修复

DFU Leave 不再依赖 ST 默认立即系统复位；启用 vendor exit 回调，由 loader 主循环完成 SRAM 拷贝、boot_info JUMP、ABI token 和复位。USB 配置后最多等待一个2000ms窗口发起下载，若未下载仍自动启动有效应用；下载中保持PC7长亮，空闲时闪烁。v1.1 双变体已重新构建，leave/启动待实板复测。


## 2026-11-24 QSPI 块擦除加速（v1.1）

参照官方 DaisyBootloader（HEAD `8b279a8`）：`gxseed` 的 `QSPIHandle::Erase` 改为 **64KiB 块擦除**（`BLOCK_ERASE_CMD 0xD8`，不足/不对齐回退 4KiB），`shared/dfu.cpp` 的擦除 `bwPollTimeout` 由 **8000ms 降到 200ms**。单块擦除 typ ~0.15s；standard(2000ms) 与 yola_voice(100ms) 四份 loader 均已用此版本重建，文件名/产品串/超时不变。旧扇区擦除版二进制已归档于 `dist_archive/sectorerase_v1.1_20261124/`（本地、gitignore）。库改为共享影响，需实板验证下载擦写与跳转；实板通过前不宣称已验收。
