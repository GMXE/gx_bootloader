#ifndef DSY_DFU
#define DSY_DFU

#include <cstdint>
#include "per/qspi.h"

namespace daisy
{
/** @addtogroup serial
@{
*/

/**
    @author Corvus Prudens
    @date 14 July, 2021

    @brief Presents a DFU device and endpoints to the USB host,
    and downloads an application if initiated within 5 seconds.
    Jumps to existing program after if present. Breathing LED indicates
    idle bootloader. An SOS pattern indicates the application is not
    correctly configured to run from the bootloader.
*/
class DFUHandle
{
  public:
    enum Result
    {
      OK = 0,
      ERR
    };

    /** Configuration structure for interfacing with DFU Driver */
    struct Config
    {
    };

    /** Initializes the USB drivers. */
    Result Init(QSPIHandle* qspi);

    /** Deinitializes DFU-related peripherals */
    Result DeInit();

    /** Returns true if a DFU transaction has completed */
    bool GetDfuComplete();

    /** Returns true if a DFU transaction has been initiated */
    bool GetDfuInitiated();
    bool IsUsbConfigured();
    // USB已开始枚举（ADDR 或 CONFIGURED），用于禁止启动超时抢占枚举。
    bool IsUsbEnumerating();
    uint32_t UsbEnumerationState();

    /** 最近一次主机 DFU 交互（擦/写/读/GetStatus）的 SysTick 毫秒；0 表示尚无。 */
    uint32_t LastActivityMs();

    /** QSPI 擦/写正在被主循环处理中（主机传输进行中）。 */
    bool IsBusy();

    /** 上一次 QSPI 擦/写失败，需要 Recover() 才能继续。 */
    bool HasFailed();

    /** DeInit + Init：清除失败/锁存状态并重新枚举一个干净的 DFU 会话。 */
    Result Recover();

    /** Method to call within main() while loop, or other
     *  low-priority callback that can be interrupted.
     *
     *  This method performs the actual disk I/O for the QSPI
     */
    bool ProcessIoRequests();

    DFUHandle() : pimpl_(nullptr) {}
    DFUHandle(const DFUHandle &other) = default;
    DFUHandle &operator=(const DFUHandle &other) = default;

    class Impl; /**< & */

  private:
    Impl *pimpl_;

    static constexpr uint32_t sine_fid_ = 10;
    static constexpr uint32_t sine_hz_ = 1.f;
    float angle_;
    uint32_t pwm_tick_;
};

/** @} */

} // namespace daisy

#endif // DSY_DFU
