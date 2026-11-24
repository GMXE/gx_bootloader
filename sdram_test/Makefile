# 使用同一全区自检源码，经过真实loader链，不覆盖片内Flash。
TARGET = GMXE_SdramTest_BOOT_SRAM
GXSEED_BOARD = gmxe
APP_TYPE = BOOT_SRAM
LIBDAISY_DIR = ../../libDaisy
CPP_SOURCES = $(LIBDAISY_DIR)/examples/GMXE_SdramTest/GMXE_SdramTest.cpp
SYSTEM_FILES_DIR = $(LIBDAISY_DIR)/core
LDSCRIPT = sram.lds
OPT = -O2
include $(SYSTEM_FILES_DIR)/Makefile
