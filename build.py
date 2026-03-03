#!/usr/bin/env python3
"""
Unified build script for Redis 8.6.1.

Detects the host operating system and invokes the Redis Makefile build
with the appropriate toolchain.

  - Windows: MSYS2 POSIX layer (gcc + make) — Redis requires a full POSIX
             environment (fork, sys/uio.h, etc.) and cannot be compiled with
             MSVC or native MinGW64.  The resulting .exe runs via msys-2.0.dll.
  - Linux:   make + gcc (with jemalloc)
  - macOS:   make + clang

Produces:
  - redis-server / redis-server.exe
  - redis-cli    / redis-cli.exe
  - redis-benchmark / redis-benchmark.exe

Usage:
  python build.py [--config Release|Debug] [--clean] [--jobs N] [--tls]
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD_ROOT = ROOT / "build"

REDIS_BINARIES = [
    "redis-server",
    "redis-cli",
    "redis-benchmark",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    print(msg, flush=True)


def run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None) -> None:
    log("+ " + " ".join(str(c) for c in cmd))
    merged_env = None
    if env:
        merged_env = {**os.environ, **env}
    subprocess.run(cmd, check=True, cwd=cwd, env=merged_env)


def load_root_env() -> None:
    """Load variables from the project-root .env file."""
    env_path = ROOT.parent.parent / ".env"
    if not env_path.exists():
        return
    loaded = 0
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v
            loaded += 1
    if loaded:
        log(f"[INFO] Loaded {loaded} vars from {env_path}")


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

def detect_platform() -> str:
    sys_name = platform.system().lower()
    if "windows" in sys_name:
        return "windows"
    if "darwin" in sys_name:
        return "macos"
    if "linux" in sys_name:
        return "linux"
    raise SystemExit(f"Unsupported platform: {sys_name}")


# ---------------------------------------------------------------------------
# MSYS2 detection (Windows)
# ---------------------------------------------------------------------------

MSYS2_SEARCH_ROOTS = [
    Path("C:/msys64"),
    Path("D:/msys64"),
    Path(os.environ.get("MSYS2_ROOT", "")) if os.environ.get("MSYS2_ROOT") else None,
]


def find_msys2_root() -> Path | None:
    """Find the MSYS2 installation directory.

    We need the MSYS (POSIX) environment — not MinGW64 — because Redis
    depends on POSIX APIs (fork, sys/uio.h, sys/wait.h …) that native
    MinGW64 does not provide.
    """
    for root in MSYS2_SEARCH_ROOTS:
        if root and root.exists() and (root / "usr" / "bin" / "gcc.exe").exists():
            return root
    # Fall back: accept roots that have MinGW64 gcc but not MSYS gcc
    # (the user will need to install the msys/gcc package)
    for root in MSYS2_SEARCH_ROOTS:
        if root and root.exists() and (root / "usr" / "bin" / "bash.exe").exists():
            return root
    return None


def find_msys2_bash(msys2_root: Path) -> Path:
    """Return the path to MSYS2's bash."""
    bash = msys2_root / "usr" / "bin" / "bash.exe"
    if bash.exists():
        return bash
    raise SystemExit(f"[ERROR] MSYS2 bash not found at {bash}")


# ---------------------------------------------------------------------------
# Windows: MSYS2 POSIX-layer Makefile build
# ---------------------------------------------------------------------------

def build_windows(build_dir: Path, config: str, jobs: int, tls: bool) -> None:
    msys2_root = find_msys2_root()
    if not msys2_root:
        log("[ERROR] MSYS2 not found.")
        log("        Install MSYS2 from https://www.msys2.org/")
        log("        Then run:  pacman -S gcc make")
        raise SystemExit(1)

    # Verify the MSYS (POSIX) gcc is available
    msys_gcc = msys2_root / "usr" / "bin" / "gcc.exe"
    if not msys_gcc.exists():
        log("[ERROR] MSYS2 POSIX gcc not found.")
        log("        Install it with:  pacman -S gcc make msys2-runtime-devel")
        raise SystemExit(1)

    log(f"[INFO] MSYS2 root: {msys2_root}")
    bash = find_msys2_bash(msys2_root)

    # Build Redis using MSYS2 bash in the MSYS (POSIX) environment.
    # MSYSTEM=MSYS gives us the full Cygwin-based POSIX layer that Redis
    # needs (fork, sys/uio.h, sys/wait.h, sys/un.h, termios.h, etc.).
    # The resulting binaries depend on msys-2.0.dll at runtime — just like
    # the existing Redis 7.2.4 Windows binaries in this repo.

    # Convert Windows paths to MSYS2 paths
    redis_src_msys = str(ROOT).replace("\\", "/")
    build_dir_msys = str(build_dir).replace("\\", "/")

    # Build env vars
    env_lines = ['export MALLOC=libc']  # jemalloc doesn't build well on MSYS2
    if config == "Debug":
        env_lines.append('export OPTIMIZATION="-O0"')
        env_lines.append('export REDIS_CFLAGS="-g -ggdb"')
    if tls:
        env_lines.append('export BUILD_TLS=yes')

    env_block = "\n".join(env_lines)

    script = f"""
set -e

echo "[INFO] gcc: $(gcc --version | head -1)"
echo "[INFO] make: $(make --version | head -1)"

{env_block}

cd "{redis_src_msys}"

echo "[1/4] Cleaning previous build artifacts ..."
make distclean 2>/dev/null || true

echo "[2/4] Building dependencies ..."
cd deps
# GCC 15 treats -Wchar-subscripts as error with -Werror (hiredis sds.c passes
# char to isprint/isspace ctype macros).  We suppress this by editing hiredis's
# Makefile WARNINGS in-place before building.
sed -i 's/-Werror/-Werror -Wno-error=char-subscripts/' hiredis/Makefile
make hiredis linenoise lua hdr_histogram fpconv fast_float xxhash \
     MALLOC=libc -j{jobs}
cd ..

echo "[3/4] Building Redis ..."
# Build only the server binaries via src/Makefile directly.
# Skips test module .so files which fail to link on MSYS2.
make -C src -j{jobs} MALLOC=libc \
     redis-server redis-sentinel redis-cli redis-benchmark redis-check-rdb redis-check-aof

echo "[4/4] Installing binaries ..."
mkdir -p "{build_dir_msys}/bin"
for bin in redis-server redis-cli redis-benchmark; do
    if [ -f "src/$bin.exe" ]; then
        cp -f "src/$bin.exe" "{build_dir_msys}/bin/"
    elif [ -f "src/$bin" ]; then
        cp -f "src/$bin" "{build_dir_msys}/bin/"
    fi
done

echo "[OK] Redis binaries installed to {build_dir_msys}/bin/"
"""

    build_dir.mkdir(parents=True, exist_ok=True)

    # Run under MSYS2 bash with MSYSTEM=MSYS (full POSIX environment)
    log(f"[INFO] Building Redis with MSYS2 POSIX layer ({bash}) ...")
    subprocess.run(
        [str(bash), "--login", "-c", script],
        check=True,
        env={
            **os.environ,
            "MSYSTEM": "MSYS",
            "CHERE_INVOKING": "1",  # Don't cd to home
            "HOME": str(Path.home()),
        },
    )

    # Copy MSYS2 runtime DLLs that redis-server.exe depends on
    _copy_msys2_runtime_dlls(msys2_root, build_dir / "bin")


def _copy_msys2_runtime_dlls(msys2_root: Path, bin_dir: Path) -> None:
    """Copy the MSYS2 runtime DLLs that Redis .exe files depend on.

    Binaries built under MSYSTEM=MSYS link against msys-2.0.dll (the
    Cygwin-derived POSIX emulation layer).  We also bundle the MSYS2
    builds of OpenSSL and GCC runtime when present.
    """
    msys_bin = msys2_root / "usr" / "bin"

    dll_candidates = [
        # Core POSIX emulation layer (required)
        (msys_bin / "msys-2.0.dll", True),
        # OpenSSL (needed if TLS is enabled, harmless to include)
        (msys_bin / "msys-ssl-3.dll", False),
        (msys_bin / "msys-crypto-3.dll", False),
        # GCC runtime (MSYS builds)
        (msys_bin / "msys-gcc_s-seh-1.dll", False),
        (msys_bin / "msys-stdc++-6.dll", False),
    ]

    copied = 0
    for dll_path, required in dll_candidates:
        if dll_path.exists():
            shutil.copy2(dll_path, bin_dir / dll_path.name)
            copied += 1
        elif required:
            log(f"[WARN] Required DLL not found: {dll_path}")

    if copied:
        log(f"[INFO] Copied {copied} runtime DLLs to {bin_dir}")


# ---------------------------------------------------------------------------
# Linux / macOS: traditional Makefile build
# ---------------------------------------------------------------------------

def find_make(plat: str) -> str:
    found = shutil.which("make")
    if not found:
        if plat == "macos":
            log("[ERROR] 'make' not found. Install Xcode Command Line Tools:")
            log("          xcode-select --install")
        else:
            log("[ERROR] 'make' not found. Install build-essential:")
            log("          sudo apt-get install build-essential")
        raise SystemExit(1)
    return "make"


def make_env(plat: str, config: str, tls: bool) -> dict:
    env: dict[str, str] = {}
    if plat == "linux":
        env["MALLOC"] = "jemalloc"
    else:
        env["MALLOC"] = "libc"
    if config == "Debug":
        env["OPTIMIZATION"] = "-O0"
        env["REDIS_CFLAGS"] = "-g -ggdb"
    if tls:
        env["BUILD_TLS"] = "yes"
    return env


def build_unix(plat: str, build_dir: Path, jobs: int, config: str, tls: bool) -> None:
    make_cmd = find_make(plat)
    env = make_env(plat, config, tls)

    log("\n[1/3] Building dependencies …")
    dep_args = [make_cmd, f"-j{jobs}"]
    if env.get("MALLOC") == "jemalloc":
        dep_args += ["hiredis", "jemalloc", "lua", "linenoise"]
    else:
        dep_args += ["hiredis", "lua", "linenoise"]
    run(dep_args, cwd=ROOT / "deps", env=env)

    log("\n[2/3] Building Redis …")
    make_args = [make_cmd, f"-j{jobs}"]
    for k, v in env.items():
        make_args.append(f"{k}={v}")
    run(make_args, cwd=ROOT / "src")

    log("\n[3/3] Installing binaries …")
    build_dir.mkdir(parents=True, exist_ok=True)
    install_args = [make_cmd, "install", f"PREFIX={build_dir}"]
    for k, v in env.items():
        install_args.append(f"{k}={v}")
    run(install_args, cwd=ROOT)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_binaries(build_dir: Path, plat: str) -> None:
    bin_dir = build_dir / "bin"
    ext = ".exe" if plat == "windows" else ""
    found: list[str] = []
    missing: list[str] = []

    for name in REDIS_BINARIES:
        binary = bin_dir / f"{name}{ext}"
        if binary.exists():
            size_mb = binary.stat().st_size / (1024 * 1024)
            found.append(f"  {binary.name:30s} ({size_mb:.1f} MB)")
        else:
            missing.append(name)

    if found:
        log("\n[OK] Produced binaries:")
        for line in found:
            log(line)
    if missing:
        log("\n[WARN] Missing binaries:")
        for name in missing:
            log(f"  {name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Build Redis 8.6.1")
    parser.add_argument(
        "--config", default="Release", choices=["Release", "Debug"],
        help="Build configuration (default: Release)",
    )
    parser.add_argument("--clean", action="store_true", help="Remove build dir before building")
    parser.add_argument(
        "--jobs", type=int, default=os.cpu_count() or 4,
        help="Parallel jobs (default: cpu count)",
    )
    parser.add_argument("--tls", action="store_true", help="Build with TLS support")
    args = parser.parse_args()

    load_root_env()
    plat = detect_platform()
    build_dir = BUILD_ROOT / plat

    log(f"[INFO] Platform : {plat}")
    log(f"[INFO] Config   : {args.config}")
    log(f"[INFO] Jobs     : {args.jobs}")
    log(f"[INFO] TLS      : {'yes' if args.tls else 'no'}")
    log(f"[INFO] Build dir: {build_dir}")

    if args.clean and build_dir.exists():
        log(f"[INFO] Cleaning {build_dir} …")
        shutil.rmtree(build_dir)

    if plat == "windows":
        build_windows(build_dir, args.config, args.jobs, args.tls)
    else:
        build_unix(plat, build_dir, args.jobs, args.config, args.tls)

    verify_binaries(build_dir, plat)
    log(f"\n[OK] Redis build finished for {plat} ({args.config}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
