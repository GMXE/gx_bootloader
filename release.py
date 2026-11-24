#!/usr/bin/env python3
"""构建、检查、打包；不执行烧录或上传。"""
from pathlib import Path
import hashlib, json, shutil, struct, subprocess, tempfile
from datetime import datetime, timezone
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LIB = ROOT / "libDaisy"
APP = ROOT / "gmxe project/YOLA_VOICE_gx"
def run(args, cwd):
    subprocess.run(args, cwd=cwd, check=True)
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
run(["make", "-j4", "GXSEED_BOARD=gmxe"], LIB)
run(["make", "-j4"], ROOT / "DaisySP")
for usb_mode in ("extdfu", "intdfu"):
    run(["make", "clean", "USB_MODE="+usb_mode], HERE)
    run(["make", "-j4", "USB_MODE="+usb_mode], HERE)
run(["make", "-j4"], HERE / "sdram_test")
run(["make", "-j4"], APP)
s = (APP / "Makefile").read_text()
with tempfile.TemporaryDirectory(prefix="gmxe-ui-") as temp:
    # 当前YOLA入口已支持固件选择，直接复用ui分支，避免复制旧的条件块。
    mk = Path(temp) / "Makefile"
    mk.write_text(s)
    run(["make", "-f", str(mk), "-j4", "YOLA_FIRMWARE=ui", "BUILD_DIR=build_gmxe_boot_ui"], APP)
images = [
    (HERE / "build_gmxe_extdfu/gmxe_bootloader_v1.1-extdfu-2000ms", "gmxe_bootloader_v1.1-extdfu-2000ms", 0x08000000, 128*1024),
    (HERE / "build_gmxe_intdfu/gmxe_bootloader_v1.1-intdfu-2000ms", "gmxe_bootloader_v1.1-intdfu-2000ms", 0x08000000, 128*1024),
    (HERE / "sdram_test/build_gmxe/GMXE_SdramTest_BOOT_SRAM", "GMXE_SdramTest_BOOT_SRAM", 0x24000000, 480*1024),
    (APP / "build_gmxe/YOLA_EX_VOICE", "YOLA_VOICE_gxseed_EXPERIMENTAL", 0x24000000, 480*1024),
    (APP / "build_gmxe_boot_ui/YOLA_EX_VOICE_UI_DEBUG", "YOLA_VOICE_gxseed_UI_EXPERIMENTAL", 0x24000000, 480*1024),
]
dist = HERE / "dist"
dist.mkdir(exist_ok=True)
records = []
for stem, name, base, capacity in images:
    # 版本号含点（v1.1），不能用with_suffix否则会截断为v1。
    binary = stem.with_name(stem.name + ".bin")
    data = binary.read_bytes()
    sp, pc = struct.unpack_from("<II", data)
    if not (8 <= len(data) <= capacity and 0x20000000 < sp <= 0x20020000
            and sp % 8 == 0 and pc & 1 and base <= pc < base + len(data)):
        raise RuntimeError("镜像大小或向量表不匹配: " + str(binary))
    for ext in (".bin", ".elf", ".map"):
        shutil.copy2(stem.with_name(stem.name + ext), dist / (name + ext))
    records.append(dict(file=name+".bin", bytes=len(data), sha256=digest(binary),
                        storage_address=hex(0x08000000 if base == 0x08000000 else 0x90040000),
                        execution_address=hex(base), stack=hex(sp), reset=hex(pc)))
# 验证链接产物中没有旧板内存/音频初始化，而不是只检查main源码。
for index, expected, absent in ((0, "USBInit_HS", "USBInit_FS"), (1, "USBInit_FS", "USBInit_HS")):
    symbols = subprocess.check_output(["arm-none-eabi-nm", "-C", str(images[index][0])+".elf"], text=True)
    for forbidden in ("SdramHandle::", "DaisySeed::", "HAL_SDRAM_Init", "HAL_SAI_Init", "HAL_SD_Init"):
        if forbidden in symbols:
            raise RuntimeError("Loader包含不允许的初始化: " + forbidden)
    if expected not in symbols or absent in symbols:
        raise RuntimeError("USB编译选择不匹配: " + str(images[index][0]))
    if "USBD_DFU_GetUsrStringDesc" not in symbols:
        raise RuntimeError("DFU布局字符串索引6回调未链接: " + str(images[index][0]))
manifest = dict(created_utc=datetime.now(timezone.utc).isoformat(), board="GMXE W9825G6KH-6 x16 32MiB",
                boot_abi=1, hardware_validated=False, audio_port_complete=False,
                compiler=subprocess.check_output(["arm-none-eabi-gcc", "--version"], text=True).splitlines()[0],
                libdaisy_base=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=LIB, text=True).strip(),
                libdaisy_archive_sha256=digest(LIB / "build_gmxe/libdaisy.a"),
                sources={}, images=records)
for folder in (HERE, LIB / "src/board"):
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix in (".cpp", ".c", ".h", ".inc", ".lds", ".py") and not any(p in ("dist", "build_gmxe", "build_gmxe_extdfu", "build_gmxe_intdfu") for p in path.parts):
            manifest["sources"][str(path.relative_to(ROOT))] = digest(path)
for path in (HERE / "Makefile", LIB / "src/daisy_seed.cpp", LIB / "core/Makefile", APP / "Makefile", APP / "STM32H750IB_gmxe_sram_noitcm.lds", APP / "STM32H750IB_gmxe_sram_itcm.lds"):
    manifest["sources"][str(path.relative_to(ROOT))] = digest(path)
(dist / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
(dist / "SHA256SUMS").write_text("".join(x["sha256"]+"  "+x["file"]+"\n" for x in records))
shutil.copy2(HERE / "README.md", dist / "烧录与验证说明.md")
print("PASS: 五份镜像容量/向量表检查；双版本USB选择检查；loader不含SDRAM/音频初始化。产物: " + str(dist))
