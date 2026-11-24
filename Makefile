# 独立GMXE loader，只使用System/QSPI/USB/GPIO，无SDRAM或codec初始化。
# 构建配置：standard=通用开发板(2000ms) | yola_voice=产品专用(100ms)
PROFILE ?= standard
USB_MODE ?= extdfu
ifeq ($(USB_MODE),extdfu)
USB_EXT = 1
USB_TAG = ex
else ifeq ($(USB_MODE),intdfu)
USB_EXT = 0
USB_TAG = int
else
$(error USB_MODE must be intdfu or extdfu)
endif

ifeq ($(PROFILE),standard)
BOOT_VERSION ?= v1.1
BOOT_TIMEOUT_MS ?= 2000
TARGET = gmxe_bootloader_$(BOOT_VERSION)-$(USB_MODE)-$(BOOT_TIMEOUT_MS)ms
BUILD_DIR = build_gmxe_$(USB_MODE)
USB_DESC_DEF =
else ifeq ($(PROFILE),yola_voice)
BOOT_TIMEOUT_MS ?= 100
TARGET = yola_voice_$(USB_TAG)
BUILD_DIR = build_yola_voice_$(USB_TAG)
ifeq ($(USB_TAG),int)
USB_DESC_DEF = -DDSY_USB_DESC_PRODUCT_STR='"YOLA Voice int"'
else
USB_DESC_DEF = -DDSY_USB_DESC_PRODUCT_STR='"YOLA Voice ex"'
endif
else
$(error PROFILE must be standard or yola_voice)
endif

GXSEED_BOARD = gmxe
LIBDAISY_DIR = ../libDaisy
SYSTEM_FILES_DIR = $(LIBDAISY_DIR)/core
CPP_SOURCES = main.cpp shared/dfu.cpp
C_SOURCES = shared/usbd_desc.c $(LIBDAISY_DIR)/Middlewares/ST/STM32_USB_Device_Library/Class/DFU/Src/usbd_dfu.c
C_INCLUDES = -Ishared -I$(LIBDAISY_DIR)/Middlewares/ST/STM32_USB_Device_Library/Class/DFU/Inc
C_DEFS += -DDSY_DFU_USE_EXT_USB=$(USB_EXT) -DDSY_BOOT_TIMEOUT_MS=$(BOOT_TIMEOUT_MS) -DUSBD_DFU_VENDOR_EXIT_ENABLED=1 $(USB_DESC_DEF)
LDSCRIPT = boot_linker.lds
OPT = -O2
DEBUG = 1
include $(SYSTEM_FILES_DIR)/Makefile

# 便利目标：直接构建 YOLA Voice 专用 loader（调用 make PROFILE=yola_voice USB_MODE=...）。
.PHONY: yola_voice_int yola_voice_ex
yola_voice_int:
	$(MAKE) PROFILE=yola_voice USB_MODE=intdfu all
yola_voice_ex:
	$(MAKE) PROFILE=yola_voice USB_MODE=extdfu all
