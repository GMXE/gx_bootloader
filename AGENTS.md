# GMXE Bootloader约定
- 仅GMXE W9825G6KH-6板型；按官方编译选择生成extdfu(PB14/PB15)和intdfu(PA11/PA12)，均2000ms；不加入双口或自动切换。
- loader不得初始化SDRAM、codec、音频或SDMMC；应用在系统复位后拥有FMC和时钟。
- boot ABI v1共享libDaisy/src/board/gmxe_boot.h；最后64B backup SRAM保留，修改ABI必须同时修改库。
- release.py只构建与打包；不默认烧录、提交或上传。源码变更后重新运行并核对manifest。
- 构建通过不等于实板通过；YOLA音频适配未完成时必须保留EXPERIMENTAL标识。
