# -*- coding: utf-8 -*-
# ============================================================================
# beacon.py — 七语言协同 · MicroPython 伴生信标 (lang7)
#
# 运行在 ESP32 / RP2040 等 MicroPython 板上：作为 vivo X300 的伴生发射机，
# 周期广播「纠缠信标」——携带 EPR 共享切片 + 参数，经 WiFi UDP 组播
# 覆盖约 34 米（视距；经典电磁波，本仓库论文：经典信道模拟量子通道）。
#
# 用法（板上）:
#   import beacon
#   beacon.run(ssid="X300-Hotspot", psk="12345678",
#              group="224.0.0.34", port=34034, seed=34, period_ms=1000)
# ============================================================================
try:
    import network
    import socket
    import machine
    import time
    from beacon_lib import build_frame, crc16
except ImportError:
    # 主机端语法检查/仿真：test_host.py 会以桩模块导入本文件
    import time
    from beacon_lib import build_frame, crc16


def run(ssid="", psk="", group="224.0.0.34", port=34034,
        seed=34, meta=None, period_ms=1000, led_pin=2, max_frames=0):
    """meta: dict(seed,theta,rounds,lenA,lenB) + slices"""
    if meta is None:
        meta = {"seed": seed, "theta": 1.5707963, "rounds": 8,
                "lenA": 0, "lenB": 0}
    led = None
    try:
        led = machine.Pin(led_pin, machine.Pin.OUT)
    except Exception:
        pass

    # 连 WiFi（vivo X300 热点或局域网 AP）
    if ssid:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if not wlan.isconnected():
            wlan.connect(ssid, psk)
            for _ in range(30):
                if wlan.isconnected():
                    break
                time.sleep(0.5)
        if not wlan.isconnected():
            raise OSError("WiFi 连接失败（34m 信标需要局域网）")
        print("[beacon] WiFi ok:", wlan.ifconfig()[0])

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

    seq = 0
    while max_frames == 0 or seq < max_frames:
        # 周期广播：EPR 共享切片（演示用 64B；实际可按需扩到整文件分片）
        slice_a = bytes([ (seq * 7 + i * 3) & 0xFF for i in range(64)])
        slice_b = bytes([ (seq * 5 + i * 11) & 0xFF for i in range(64)])
        frame = build_frame(seq, meta, slice_a, slice_b)
        try:
            sock.sendto(frame, (group, port))
            if led is not None:
                led.value(1)
                time.sleep_ms(10)
                led.value(0)
            print("[beacon] tx seq=%d %d B → %s:%d" % (seq, len(frame), group, port))
        except OSError as e:
            print("[beacon] tx fail:", e)
        seq += 1
        time.sleep_ms(period_ms)
    sock.close()
