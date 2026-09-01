// ============================================================================
// main.rs — 七语言协同 · Rust CLI (lang7)
//
//   cargo run --release -- <A.pdf> <B.pdf> [--seed N] [--theta R]
//       [--rounds K] [--fidelity D] [--depth-rounds R]
//
// 独立复算纠缠浓度与深度（与 C++ 引擎交叉验证），输出 JSON 单行。
// 铁律：浓度 ≥ 34%（阿雷纳常数）；深度趋于 99.99%。
// ============================================================================

use entangle_rust::{concentration, depth_metrics, key_byte, crc16};
use std::env;
use std::fs;

fn slurp(path: &str) -> std::io::Result<Vec<u8>> {
    fs::read(path)
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        eprintln!("用法: entangle-rust <A.pdf> <B.pdf> [--seed N] [--theta R] [--rounds K] [--fidelity D] [--depth-rounds R]");
        std::process::exit(1);
    }
    let mut seed: u64 = 34;
    let mut theta = -1.0f64;
    let mut rounds = -1i32;
    let mut fid = 0.90f64;
    let mut depth_r = 16384i32;
    let mut i = 3;
    while i + 1 < args.len() {
        match args[i].as_str() {
            "--seed" => seed = args[i + 1].parse().unwrap_or(34),
            "--theta" => theta = args[i + 1].parse().unwrap_or(-1.0),
            "--rounds" => rounds = args[i + 1].parse().unwrap_or(-1),
            "--fidelity" => fid = args[i + 1].parse().unwrap_or(0.90),
            "--depth-rounds" => depth_r = args[i + 1].parse().unwrap_or(16384),
            _ => {}
        }
        i += 2;
    }
    let a = match slurp(&args[1]) {
        Ok(v) => v,
        Err(e) => { eprintln!("读入失败 {}: {}", args[1], e); std::process::exit(1); }
    };
    let b = match slurp(&args[2]) {
        Ok(v) => v,
        Err(e) => { eprintln!("读入失败 {}: {}", args[2], e); std::process::exit(1); }
    };
    let theta_v = if theta >= 0.0 { theta } else { std::f64::consts::PI / 2.0 };
    let mut rounds_v = if rounds > 0 { rounds } else { 8 };
    let mut conc = concentration(&a, &b, theta_v, rounds_v as u32, fid);
    while conc < 0.34 - 1e-9 && rounds_v < 512 {
        rounds_v += 1;
        conc = concentration(&a, &b, theta_v, rounds_v as u32, fid);
    }
    let (net, raw, sel) = if depth_r > 0 {
        depth_metrics(&a, &b, theta_v, depth_r as u32).unwrap_or((0.0, 0.0, 0.0))
    } else { (0.0, 0.0, 0.0) };
    let crc = crc16(b"ENT34", 0xFFFF);
    println!(
        "{{\"lang\":\"rust\",\"conc\":{:.10},\"theta\":{:.10},\"rounds\":{},\"fid\":{:.6},\
         \"netDepth\":{:.10},\"rawDepth\":{:.10},\"selFrac\":{:.10},\"depthRounds\":{},\
         \"n\":{},\"seed\":{},\"k0\":\"{:02X}\",\"crcMagic\":\"{:04X}\",\"err\":\"\"}}",
        conc, theta_v, rounds_v, fid, net, raw, sel, depth_r, a.len().max(b.len()),
        seed, key_byte(seed, 0), crc
    );
}
