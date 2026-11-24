# 双版本loader SDRAM审核 · 2026-11-15

结论：两份loader使用相同启动交接，无FMC/SDRAM初始化；分别按官方宏选择USB FS或HS片内PHY，等待2000ms。无需因为选择USB口而改变SDRAM参数。

- 固定板型GMXE、W9825G6KH-6 x16 32MiB；不是官方Daisy Seed镜像。
- libDaisy/src/board/gmxe_sdram.inc：Bank1、13行、9列、4bank、16bit，39条FMC线。100MHz候选时序2/8/5/7/3/2/2，CL3、MRS0x232，8次刷新，COUNT761；未在本轮修改。
- 库与应用32MiB linker/MPU必须配套；YOLA产品/UI均需重新链接配套GMXE库。
- loader的data/bss在AXI SRAM上部32KiB，应用镜像在前480KiB NOLOAD；系统复位后镜像保留，loader在外设初始化之前跳转，避免应用与loader争用FMC。
- ABI邮箱占backup SRAM最后64B，库与loader均检查；应用配置System/MPU后消费一次性令牌，禁止已启用FMC的冷初始化。
- loader不初始化codec/audio/SDMMC，避免原Daisy板初始化配置作用于新板；这是现有GMXE实现，不等于官方全功能等价版。
- LED测试不初始化SDRAM，只能证明基本loader执行链。必须另烧32MiB全区自检，SWD检查gmxe_sdram_report，才能验收本轮SDRAM读写。
- SDRAM接管波形、真实SDCLK、温压/保持/多次冷启动及负载测试仍待实板。代码READY/编译通过不代表硬件验收。

release.py分别检查两版loader无SdramHandle/DaisySeed/HAL_SDRAM_Init/HAL_SAI_Init/HAL_SD_Init符号，且只链接所选USBInit函数；同时检查五份镜像的容量、初始栈和复位向量。manifest记录来源和SHA256。
