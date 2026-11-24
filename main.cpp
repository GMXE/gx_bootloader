// GMXE BOOT_SRAM专用：沿用官方 boot_info 复位交接，只替换板级内存配置。
#include "sys/system.h"
#include "per/qspi.h"
#include "per/gpio.h"
#include "hid/switch.h"
#include "board/gmxe_boot.h"
#include "shared/dfu.h"
#include <cstring>
using namespace daisy;
static_assert(GXSEED_BOARD_ID == 1, "GMXE profile required");
static_assert(DSY_BOOT_TIMEOUT_MS == 2000 || DSY_BOOT_TIMEOUT_MS == 100, "Timeout must be 2000ms (standard) or 100ms (yola_voice)");
constexpr uint32_t kImage = 0x90040000u;
constexpr uint32_t kSram = 0x24000000u;
constexpr uint32_t kCapacity = 480u * 1024u;
// 自动启动硬上限：未真正开始下载时，最多等这么久就尝试启动应用，
// 避免 USB 枚举/状态轮询把超时无限推迟（对齐官方固定超时语义）。
constexpr uint32_t kMaxLoadWaitMs = 10000u;
uint8_t __attribute__((section(".sram_exec"), aligned(32))) app_image[kCapacity];
System sys;
QSPIHandle qspi;
DFUHandle dfu;
GPIO led;
Switch button;
// 初始化失败用固定闪烁码提示（N 次短闪+停顿），避免与运行态混淆。
__attribute__((noreturn)) static void InitFailBlink(uint32_t count)
{
    for(;;)
    {
        for(uint32_t i=0; i<count; ++i)
        {
            led.Write(true);  System::Delay(80);
            led.Write(false); System::Delay(120);
        }
        System::Delay(800);
    }
}
// 只接受本工作区linker的DTCM栈和SRAM复位入口，不支持QSPI XIP。
static bool ValidVectors(uint32_t address)
{
    auto v=reinterpret_cast<volatile uint32_t*>(address);
    return v[0]>0x20000000u && v[0]<=0x20020000u && (v[0]&7u)==0
        && (v[1]&1u) && v[1]>=kSram && v[1]<kSram+kCapacity;
}
// 设置MSP后禁止编译器再访问旧栈。
__attribute__((naked, noreturn)) static void Jump(uint32_t stack, uint32_t entry)
{
    __asm volatile("msr msp, r0\n bx r1");
}
int main()
{
    System::InitBackupSram();
    boot_info.version=System::BootInfo::Version::v6_1;
    // 官方 loader 在复位入口优先消费 JUMP；请求令牌只用于排除ROM DFU后残留的旧mailbox。
    const bool handoff_requested=gxseed::HasBootToken(gxseed::kBootRequest);
    if(handoff_requested && boot_info.status==System::BootInfo::Type::JUMP
       && boot_info.data==kSram && ValidVectors(kSram))
    {
        boot_info.status=System::BootInfo::Type::INVALID;
        // 应用随后自行初始化GMXE时钟/MPU/FMC；loader不触碰SDRAM。
        gxseed::SetBootToken(gxseed::kBootReady);
        SCB->VTOR=kSram; __DSB(); __ISB();
        auto v=reinterpret_cast<volatile uint32_t*>(kSram);
        Jump(v[0],v[1]);
    }
    gxseed::SetBootToken(0);
    const bool infinite=boot_info.status==System::BootInfo::Type::INF_TIMEOUT;
    const uint32_t timeout=boot_info.status==System::BootInfo::Type::SKIP_TIMEOUT ? 100u : DSY_BOOT_TIMEOUT_MS;
    boot_info.status=System::BootInfo::Type::INVALID;
    System::Config cfg; cfg.Boost(); cfg.use_dcache=false;
    sys.Init(cfg);
    QSPIHandle::Config q;
    q.device=QSPIHandle::Config::Device::IS25LP064A;
    q.mode=QSPIHandle::Config::Mode::MEMORY_MAPPED;
    q.pin_config.io0=Pin(PORTF,8); q.pin_config.io1=Pin(PORTF,9);
    q.pin_config.io2=Pin(PORTF,7); q.pin_config.io3=Pin(PORTF,6);
    q.pin_config.clk=Pin(PORTF,10); q.pin_config.ncs=Pin(PORTG,6);
    led.Init(Pin(PORTC,7),GPIO::Mode::OUTPUT);
    // 官方 Daisy Seed：BOOT 按键经 PG3 读取；复位后按住 BOOT 即保持 DFU。
    // 与官方 Daisy loader 一致：PG3/BOOT 使用正常极性，按下为高电平。
    // 用内部下拉避免 PG3 浮空被误判为“按住 BOOT”而永不自动启动。
    button.Init(Pin(PORTG,3), 1000.0f, Switch::TYPE_MOMENTARY,
                Switch::POLARITY_NORMAL, GPIO::Pull::PULLDOWN);
    if(qspi.Init(q)!=QSPIHandle::Result::OK || dfu.Init(&qspi)!=DFUHandle::Result::OK)
        InitFailBlink(3);

    const uint32_t start=System::GetNow();
    uint32_t usb_configured_at=0;
    uint32_t usb_addressed_at=0;
    bool usb_was_enumerating=false;
    bool usb_was_configured=false;
    bool boot_button_pressed=false;
    uint32_t failed_at=0;
    for(;;)
    {
        dfu.ProcessIoRequests();
        button.Debounce();
        if(button.RisingEdge()) boot_button_pressed=true;

        // 一次擦/写失败不应永久锁死：冷却后重新枚举一个干净的 DFU 会话。
        if(dfu.HasFailed())
        {
            if(failed_at==0) failed_at=System::GetNow();
            if(System::GetNow()-failed_at>=1000)
            {
                dfu.Recover();
                failed_at=0;
                usb_was_configured=false;
                usb_configured_at=0;
            }
        }
        else failed_at=0;

        const bool usb_active=dfu.IsUsbConfigured();
        const bool usb_enumerating=dfu.IsUsbEnumerating();
        if(usb_active && !usb_was_configured) usb_configured_at=System::GetNow();
        if(usb_enumerating && !usb_was_enumerating) usb_addressed_at=System::GetNow();
        if(!usb_enumerating) usb_addressed_at=0;
        usb_was_enumerating=usb_enumerating;
        usb_was_configured=usb_active;

        // LED：传输中快闪，失败急闪，已配置常亮，等待慢闪。
        if(dfu.IsBusy())         led.Write(((System::GetNow()/100u)&1u));
        else if(dfu.HasFailed()) led.Write(((System::GetNow()/80u)&1u));
        else if(usb_active)      led.Write(true);
        else                     led.Write(((System::GetNow()/250u)&1u));

        // 下载完成（DFU leave/manifest）：拷贝到 SRAM 后复位交给应用。
        if(dfu.GetDfuComplete())
        {
            // 先把最后一笔异步擦/写落盘，避免从 QSPI 拷贝到未写完的镜像。
            while(dfu.IsBusy()) dfu.ProcessIoRequests();
            if(dfu.HasFailed())
            {
                dfu.Recover();
                usb_was_configured=false;
                usb_configured_at=0;
                continue;
            }
            if(ValidVectors(kImage))
            {
                // DFU_Leave 已 USBD_Stop；等断开稳定后拷贝并跳转。
                System::Delay(50);
                std::memcpy(app_image,reinterpret_cast<const void*>(kImage),kCapacity);
                qspi.DeInit();
                boot_info.data=kSram;
                boot_info.status=System::BootInfo::Type::JUMP;
                gxseed::SetBootToken(gxseed::kBootRequest);
                led.Write(false);
                HAL_NVIC_SystemReset();
            }
            dfu.Recover(); // 无效镜像：重新枚举，继续等待
            continue;
        }

        // 自动启动：对齐官方固定超时语义。只有“真正开始下载”或按住 BOOT 才抑制；
        // 不再用每次 GETSTATUS 的活动时间续命；再加硬上限，防止 USB 枚举把启动无限推迟。
        uint32_t base=start;
        if(usb_addressed_at>base) base=usb_addressed_at;
        if(usb_configured_at>base) base=usb_configured_at;
        const uint32_t now=System::GetNow();
        const bool elapsed=now-base>=timeout;
        const bool hard_cap=now-start>=kMaxLoadWaitMs;
        const bool downloading=dfu.GetDfuInitiated();
        if(!infinite && !downloading && !boot_button_pressed && !dfu.IsBusy()
           && (elapsed || hard_cap) && ValidVectors(kImage))
        {
            led.Write(false);
            dfu.DeInit();
            std::memcpy(app_image,reinterpret_cast<const void*>(kImage),kCapacity);
            qspi.DeInit();
            boot_info.data=kSram;
            boot_info.status=System::BootInfo::Type::JUMP;
            gxseed::SetBootToken(gxseed::kBootRequest);
            HAL_NVIC_SystemReset();
        }
    }
}
