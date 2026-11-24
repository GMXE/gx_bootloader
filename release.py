#!/usr/bin/env python3
"""构建、检查、打包 bootloader；不构建产品/自检固件，不执行烧录或上传。"""
from pathlib import Path
import hashlib, json, shutil, struct, subprocess
from datetime import datetime, timezone
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LIB = ROOT / "libDaisy"
def run(args, cwd):
    subprocess.run(args, cwd=cwd, check=True)
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
run(["make", "-j4", "GXSEED_BOARD=gmxe"], LIB)
for profile, usb_mode in (("standard", "extdfu"), ("standard", "intdfu"),
                          ("yola_voice", "intdfu"), ("yola_voice", "extdfu")):
    run(["make", "clean", "PROFILE="+profile, "USB_MODE="+usb_mode], HERE)
    run(["make", "-j4", "PROFILE="+profile, "USB_MODE="+usb_mode], HERE)
images = [
    (HERE / "build_gmxe_extdfu/gmxe_bootloader_v1.1-extdfu-2000ms", "gmxe_bootloader_v1.1-extdfu-2000ms", 0x08000000, 128*1024),
    (HERE / "build_gmxe_intdfu/gmxe_bootloader_v1.1-intdfu-2000ms", "gmxe_bootloader_v1.1-intdfu-2000ms", 0x08000000, 128*1024),
    (HERE / "build_yola_voice_int/yola_voice_int", "yola_voice_int", 0x08000000, 128*1024),
    (HERE / "build_yola_voice_ex/yola_voice_ex", "yola_voice_ex", 0x08000000, 128*1024),
]
dist = HERE / "dist"
# 只发布bootloader：重建dist，避免残留旧自检/产品固件。
if dist.exists():
    shutil.rmtree(dist)
dist.mkdir()
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
loader_checks = (
    (0, "USBInit_HS", "USBInit_FS"),  # standard extdfu (PB14/PB15)
    (1, "USBInit_FS", "USBInit_HS"),  # standard intdfu (PA11/PA12)
    (2, "USBInit_FS", "USBInit_HS"),  # yola_voice_int (PA11/PA12)
    (3, "USBInit_HS", "USBInit_FS"),  # yola_voice_ex (PB14/PB15)
)
for index, expected, absent in loader_checks:
    symbols = subprocess.check_output(["arm-none-eabi-nm", "-C", str(images[index][0])+".elf"], text=True)
    for forbidden in ("SdramHandle::", "DaisySeed::", "HAL_SDRAM_Init", "HAL_SAI_Init", "HAL_SD_Init"):
        if forbidden in symbols:
            raise RuntimeError("Loader包含不允许的初始化: " + forbidden)
    if expected not in symbols or absent in symbols:
        raise RuntimeError("USB编译选择不匹配: " + str(images[index][0]))
    if "USBD_DFU_GetUsrStringDesc" not in symbols:
        raise RuntimeError("DFU布局字符串索引6回调未链接: " + str(images[index][0]))
manifest = dict(created_utc=datetime.now(timezone.utc).isoformat(), board="GMXE W9825G6KH-6 x16 32MiB",
                boot_abi=1, hardware_validated=False,
                compiler=subprocess.check_output(["arm-none-eabi-gcc", "--version"], text=True).splitlines()[0],
                libdaisy_base=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=LIB, text=True).strip(),
                libdaisy_archive_sha256=digest(LIB / "build_gmxe/libdaisy.a"),
                sources={}, images=records)
for folder in (HERE, LIB / "src/board"):
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix in (".cpp", ".c", ".h", ".inc", ".lds", ".py") and not any(p in ("dist", "build_gmxe", "build_gmxe_extdfu", "build_gmxe_intdfu", "build_yola_voice_int", "build_yola_voice_ex") for p in path.parts):
            manifest["sources"][str(path.relative_to(ROOT))] = digest(path)
for path in (HERE / "Makefile", LIB / "src/daisy_seed.cpp", LIB / "core/Makefile"):
    manifest["sources"][str(path.relative_to(ROOT))] = digest(path)
(dist / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
(dist / "SHA256SUMS").write_text("".join(x["sha256"]+"  "+x["file"]+"\n" for x in records))
shutil.copy2(HERE / "README.md", dist / "烧录与验证说明.md")
print("PASS: 四份镜像容量/向量表检查；四版本loader USB选择检查；loader不含SDRAM/音频初始化。产物: " + str(dist))
