# 独立GMXE loader，只使用System/QSPI/USB/GPIO，无SDRAM或codec初始化。
USB_MODE ?= extdfu
ifeq ($(USB_MODE),extdfu)
USB_EXT = 1
else ifeq ($(USB_MODE),intdfu)
USB_EXT = 0
else
$(error USB_MODE must be intdfu or extdfu)
endif
BOOT_VERSION ?= v1.1
TARGET = gmxe_bootloader_$(BOOT_VERSION)-$(USB_MODE)-2000ms
BUILD_DIR = build_gmxe_$(USB_MODE)
GXSEED_BOARD = gmxe
LIBDAISY_DIR = ../libDaisy
SYSTEM_FILES_DIR = $(LIBDAISY_DIR)/core
CPP_SOURCES = main.cpp shared/dfu.cpp
C_SOURCES = shared/usbd_desc.c $(LIBDAISY_DIR)/Middlewares/ST/STM32_USB_Device_Library/Class/DFU/Src/usbd_dfu.c
C_INCLUDES = -Ishared -I$(LIBDAISY_DIR)/Middlewares/ST/STM32_USB_Device_Library/Class/DFU/Inc
C_DEFS += -DDSY_DFU_USE_EXT_USB=$(USB_EXT) -DDSY_BOOT_TIMEOUT_MS=2000 -DUSBD_DFU_VENDOR_EXIT_ENABLED=1
LDSCRIPT = boot_linker.lds
OPT = -O2
DEBUG = 1
include $(SYSTEM_FILES_DIR)/Makefile
