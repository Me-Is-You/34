// ============================================================================
// lib.rs — 七语言协同 · Rust 纠缠数学模块 (lang7)
//
// 与 C 核心 (c_cpp/entangle_core.c) 同源实现：
//   * 秩配对 (rank pairing)
//   * 布洛赫球映射 + 纠缠门 U(θ) → 并发度 C(θ)
//   * Procrustean 浓缩 + 多轮蒸馏 → 纠缠浓度 conc(θ,R)
//   * 深度指标（netDepth ≥ 99.99% / rawDepth / selFrac）
//   * EPR 共享密钥 K[r] = splitmix64(seed ⊕ r·φ)
//   * CRC-16/CCITT-FALSE（34 米信号波帧校验）
//
// 交叉验证：cargo test 会把本模块结果与 golden 常量（由 C/Python 生成）
// 逐位比较；cargo build --release 产出 libentangle_rust.so，
// Python 编排器经 ctypes 加载做独立复核（跨语言互证）。
//
// 铁律：浓度 ≥ 34%（阿雷纳常数）；深度趋于 99.99%。
// ============================================================================

const PI: f64 = 3.14159265358979323846;
const ARENA: f64 = 0.34;
const DEPTH_TARGET: f64 = 0.9999;

/// splitmix64 PRF（与 C 的 ec_splitmix64 一致）
#[inline]
pub fn splitmix64(mut x: u64) -> u64 {
    x = x.wrapping_add(0x9E3779B97F4A7C15);
    x = (x ^ (x >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
    x = (x ^ (x >> 27)).wrapping_mul(0x94D049BB133111EB);
    x ^ (x >> 31)
}

/// EPR 共享密钥第 r 个字节：K[r] = splitmix64(seed ⊕ r·φ) 高 8 位
#[inline]
pub fn key_byte(seed: u64, r: u64) -> u8 {
    let x = seed ^ (r.wrapping_mul(0x9E3779B97F4A7C15));
    (splitmix64(x) >> 56) as u8
}

/// 字节 → 布洛赫球相位 φ_x = π·x / 510 ∈ [0, π/2]
#[inline]
pub fn phi(x: u8) -> f64 {
    PI * (x as f64) / 510.0
}

/// 并发度 C(θ) = 2|αδ − βγ|
pub fn concurrence(x: u8, y: u8, theta: f64) -> f64 {
    let (fa, fb) = (phi(x), phi(y));
    let (cfa, sfa, cfb, sfb) = (fa.cos(), fa.sin(), fb.cos(), fb.sin());
    let xv = cfa * sfb;
    let yv = sfa * cfb;
    let ad = (cfa * cfb) * (sfa * sfb);
    let (c2, s2) = ((2.0 * theta).cos(), (2.0 * theta).sin());
    let bg = xv * yv * c2 + (yv * yv - xv * xv) * s2 * 0.5;
    2.0 * (ad - bg).abs()
}

/// 单轮 Procrustean 浓缩成功概率 p = 1 − √(1 − C²)
pub fn one_round_prob(c: f64) -> f64 {
    let v = 1.0 - c * c;
    if v <= 0.0 { 1.0 } else { 1.0 - v.sqrt() }
}

/// 秩配对：返回两个排列（第 r 小字节在原数组中的索引）
pub fn rank_pair(a: &[u8], b: &[u8]) -> (Vec<u32>, Vec<u32>) {
    let n = a.len().max(b.len());
    let mut pa: Vec<u32> = (0..n as u32).collect();
    let mut pb: Vec<u32> = (0..n as u32).collect();
    let key = |arr: &[u8], i: u32| arr[i as usize % arr.len()];
    pa.sort_by_key(|&i| (key(a, i), i));
    pb.sort_by_key(|&i| (key(b, i), i));
    (pa, pb)
}

/// 纠缠浓度：conc(θ,R) = mean_i[ 1 − Π_{r=1..R}(1 − p_i·d^r) ]
pub fn concentration(a: &[u8], b: &[u8], theta: f64, rounds: u32, fid: f64) -> f64 {
    let (pa, pb) = rank_pair(a, b);
    let n = pa.len();
    if n == 0 { return 0.0; }
    let (c2, s2) = ((2.0 * theta).cos(), (2.0 * theta).sin());
    let mut tot = 0.0;
    for i in 0..n {
        let x = a[pa[i] as usize % a.len()];
        let y = b[pb[i] as usize % b.len()];
        let (fa, fb) = (phi(x), phi(y));
        let (cfa, sfa, cfb, sfb) = (fa.cos(), fa.sin(), fb.cos(), fb.sin());
        let xv = cfa * sfb;
        let yv = sfa * cfb;
        let ad = (cfa * cfb) * (sfa * sfb);
        let bg = xv * yv * c2 + (yv * yv - xv * xv) * s2 * 0.5;
        let c = 2.0 * (ad - bg).abs();
        let p = one_round_prob(c);
        let mut fail = 1.0;
        let mut dp = fid;
        for _ in 1..=rounds {
            fail *= 1.0 - p * dp;
            dp *= fid;
            if fail < 1e-12 { fail = 0.0; break; }
        }
        tot += 1.0 - fail;
    }
    tot / n as f64
}

/// 深度指标：netDepth（所选子集平均，≥99.99%）、rawDepth、selFrac
pub fn depth_metrics(a: &[u8], b: &[u8], theta: f64, rounds: u32)
    -> Option<(f64, f64, f64)> {
    let (pa, pb) = rank_pair(a, b);
    let n = pa.len();
    if n == 0 { return None; }
    let (c2, s2) = ((2.0 * theta).cos(), (2.0 * theta).sin());
    let mut s: Vec<f64> = Vec::with_capacity(n);
    let mut raw_sum = 0.0;
    for i in 0..n {
        let x = a[pa[i] as usize % a.len()];
        let y = b[pb[i] as usize % b.len()];
        let (fa, fb) = (phi(x), phi(y));
        let (cfa, sfa, cfb, sfb) = (fa.cos(), fa.sin(), fb.cos(), fb.sin());
        let xv = cfa * sfb;
        let yv = sfa * cfb;
        let ad = (cfa * cfb) * (sfa * sfb);
        let bg = xv * yv * c2 + (yv * yv - xv * xv) * s2 * 0.5;
        let c = 2.0 * (ad - bg).abs();
        let p = one_round_prob(c);
        let si = if p <= 0.0 { 0.0 } else { 1.0 - (1.0 - p).powi(rounds as i32) };
        raw_sum += si;
        s.push(si);
    }
    let raw_depth = raw_sum / n as f64;
    s.sort_by(|x, y| y.partial_cmp(x).unwrap());
    let mut cum = 0.0;
    let mut k = 0usize;
    for i in 0..n {
        cum += s[i];
        if cum / (i + 1) as f64 < DEPTH_TARGET - 1e-12 { k = i; break; }
        k = i + 1;
    }
    if k == 0 { return None; }
    let net_depth = s[..k].iter().sum::<f64>() / k as f64;
    if net_depth < DEPTH_TARGET - 1e-12 { return None; }
    Some((net_depth, raw_depth, k as f64 / n as f64))
}

/// CRC-16/CCITT-FALSE（与 C/MicroPython/Verilog 同算法）
pub fn crc16(data: &[u8], mut crc: u16) -> u16 {
    for &byte in data {
        crc ^= (byte as u16) << 8;
        for _ in 0..8 {
            crc = if crc & 0x8000 != 0 { (crc << 1) ^ 0x1021 } else { crc << 1 };
        }
    }
    crc
}

/// EPR 共享生成：shareX[i] = 原文[i] ⊕ K[rankX(i)]（与 C 的 ec_epr_shares 一致）
pub fn epr_shares(seed: u64, a: &[u8], b: &[u8]) -> (Vec<u8>, Vec<u8>) {
    let (pa, pb) = rank_pair(a, b);
    let n = pa.len();
    let mut ra = vec![0u32; a.len()];
    let mut rb = vec![0u32; b.len()];
    for r in 0..n {
        let ia = pa[r] as usize;
        let ib = pb[r] as usize;
        if ia < a.len() { ra[ia] = r as u32; }
        if ib < b.len() { rb[ib] = r as u32; }
    }
    let mut sa = a.to_vec();
    let mut sb = b.to_vec();
    for i in 0..a.len() { sa[i] ^= key_byte(seed, ra[i] as u64); }
    for i in 0..b.len() { sb[i] ^= key_byte(seed, rb[i] as u64); }
    (sa, sb)
}

// ============================ FFI（Python ctypes 加载） =====================

/// 独立浓度复核（跨语言互证）：返回 concentration(...)
#[no_mangle]
pub extern "C" fn rs_concentration(
    pa: *const u8, na: usize, pb: *const u8, nb: usize,
    theta: f64, rounds: i32, fid: f64,
) -> f64 {
    if pa.is_null() || pb.is_null() { return f64::NAN; }
    let a = unsafe { std::slice::from_raw_parts(pa, na) };
    let b = unsafe { std::slice::from_raw_parts(pb, nb) };
    concentration(a, b, theta, rounds.max(1) as u32, fid)
}

/// EPR 密钥字节（跨语言对照）：K[r]
#[no_mangle]
pub extern "C" fn rs_key_byte(seed: u64, r: u64) -> u8 {
    key_byte(seed, r)
}

#[cfg(test)]
mod tests {
    use super::*;

    // golden 常量由 C 核心 / Python 孪生生成（跨语言互证）
    #[test]
    fn golden_key_bytes() {
        // 真实 golden（C 核心 ec_key_byte(34, r) 与 Python 复核一致）：
        let expect: [u8; 8] = [0x89, 0xCE, 0x1F, 0xC4, 0x31, 0xCF, 0x01, 0x4A];
        for (r, &v) in expect.iter().enumerate() {
            assert_eq!(key_byte(34, r as u64), v, "key_byte(34,{r})");
        }
    }

    #[test]
    fn crc16_known() {
        // "123456789" 的 CRC-16/CCITT-FALSE = 0x29B1
        assert_eq!(crc16(b"123456789", 0xFFFF), 0x29B1);
    }

    #[test]
    fn concentration_sanity() {
        // 全零 vs 全零：C(θ)=0 → 浓度趋近 0（可证伪：0% 输入 → 拒绝）
        let conc = concentration(&[0u8; 64], &[0u8; 64], PI / 2.0, 8, 0.9);
        assert!(conc < 0.01, "all-zero concentration should be ~0, got {conc}");
        // 随机文件（seed 固定）：浓度应在 (0,1)
        let a: Vec<u8> = (0..512u32).map(|i| (i.wrapping_mul(0x9E3779B9) >> 24) as u8).collect();
        let conc = concentration(&a, &a, PI / 2.0, 8, 0.9);
        assert!((0.0..1.0).contains(&conc));
        assert!(conc >= ARENA, "concentration must be >= 34%");
    }
}
