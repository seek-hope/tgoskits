#!/usr/bin/env bash
#
# Prepares the persistent rootfs overlay for the x86_64 StarryOS self-build app.
# The app runner owns rootfs injection and QEMU startup; this script only stages
# the exact current checkout and the guest-side runner.

set -euo pipefail

app_dir="${STARRY_APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
workspace="${STARRY_WORKSPACE:?STARRY_WORKSPACE is required}"
rootfs="${STARRY_ROOTFS:?STARRY_ROOTFS is required}"
overlay_dir="${STARRY_OVERLAY_DIR:?STARRY_OVERLAY_DIR is required}"
arch="${STARRY_ARCH:?STARRY_ARCH is required}"
rootfs_size_mib="${SELFHOST_ROOTFS_SIZE_MIB:-32768}"
output_dir="$workspace/target/starry-selfhost-x86_64"

require_x86_64() {
    if [[ "$arch" != "x86_64" ]]; then
        echo "selfhost prebuild only supports x86_64, got $arch" >&2
        exit 2
    fi
}

git_value() {
    local fallback="$1"
    shift
    git -C "$workspace" "$@" 2>/dev/null || printf '%s\n' "$fallback"
}

source_dirty() {
    if [[ -n "$(git -C "$workspace" status --porcelain --untracked-files=all)" ]]; then
        printf '%s\n' true
    else
        printf '%s\n' false
    fi
}

resize_rootfs() {
    cargo xtask image resize "$rootfs" --size-mib "$rootfs_size_mib"
}

stage_source_archive() {
    local source_tar="$output_dir/tgoskits-src.tar"

    tar -C "$workspace" \
        --exclude=.git \
        --exclude=target \
        --exclude=tmp \
        --exclude=.tgos-images \
        --exclude=.cache \
        --exclude=download \
        --exclude=.idea \
        --exclude=.vscode \
        -cf "$source_tar" .
    install -m 0644 "$source_tar" "$overlay_dir/opt/tgoskits-src.tar"
}

stage_source_metadata() {
    local metadata="$output_dir/tgoskits-src.meta"

    cat >"$metadata" <<EOF
commit=$(git_value unknown rev-parse HEAD)
ref=$(git_value detached symbolic-ref --quiet --short HEAD)
dirty=$(source_dirty)
generated_by=apps/starry/selfhost/selfhost-full-kernel/prebuild.sh
EOF
    install -m 0644 "$metadata" "$overlay_dir/opt/tgoskits-src.meta"
}

stage_guest_resolver() {
    local resolver="$overlay_dir/etc/resolv.conf"
    local resolver_source

    mkdir -p "$(dirname "$resolver")"
    : >"$resolver"
    for resolver_source in /run/systemd/resolve/resolv.conf /etc/resolv.conf; do
        [[ -f "$resolver_source" ]] || continue
        awk '
            $1 == "nameserver" && $2 !~ /^127\./ && $2 !~ /:/ && $2 != "10.0.2.3" {
                print
            }
        ' "$resolver_source" >>"$resolver"
        if [[ -s "$resolver" ]]; then
            return
        fi
    done

    cat >"$resolver" <<'EOF'
nameserver 1.1.1.1
nameserver 8.8.8.8
EOF
}

stage_guest_runner() {
    install -m 0755 "$app_dir/guest-selfbuild.sh" "$overlay_dir/opt/starry-selfhost-run.sh"
}

stage_guest_reboot_guard() {
    local profile_dir="$overlay_dir/etc/profile.d"

    mkdir -p "$profile_dir"
    install -m 0644 \
        "$app_dir/guest-selfbuild-reboot-guard.sh" \
        "$profile_dir/starry-selfhost-reboot-guard.sh"
}

stage_run_state() {
    local run_id

    run_id="$(git_value unknown rev-parse --short=12 HEAD)-$(date -u +%Y%m%dT%H%M%SZ)-$$"
    printf '%s\n' "$run_id" >"$overlay_dir/opt/starry-selfhost.run-id"
    printf 'ready %s prebuild\n' "$run_id" >"$overlay_dir/opt/starry-selfhost.state"
}

# Install the Rust toolchain on the host via rustup and inject the result as
# a single uncompressed tar.  Host-side rustup produces a properly merged
# toolchain tree (unlike manual tarball extraction, which leaves each
# component in its own subdirectory).  The guest just needs `tar xf`.
stage_rust_toolchain() {
    local toolchain_name="nightly-2026-05-28-x86_64-unknown-linux-musl"
    local output_tar="$output_dir/rust-toolchain.tar"

    if [ -f "$output_tar" ] && [ "$(stat -c%s "$output_tar" 2>/dev/null)" -gt 500000000 ]; then
        echo "[prebuild] rust toolchain tar already built ($(du -h "$output_tar" | cut -f1)) — skipping"
        install -m 0644 "$output_tar" "$overlay_dir/opt/rust-toolchain.tar"
        return
    fi

    echo "[prebuild] installing Rust musl toolchain on host via rustup..."
    # Install the minimal musl toolchain (cross-compilation — binaries are
    # glibc-linked on the host, std libs are for musl).
    rustup toolchain install "$toolchain_name" --profile minimal --force-non-host 2>/dev/null || {
        echo "[prebuild] ERROR: failed to install $toolchain_name via rustup" >&2
        exit 1
    }

    # Add the extra components and the bare-metal target.
    rustup component add --toolchain "$toolchain_name" rust-src llvm-tools-preview 2>/dev/null || true
    rustup target add --toolchain "$toolchain_name" x86_64-unknown-none 2>/dev/null || true

    local src_dir="$HOME/.rustup/toolchains/$toolchain_name"
    [ -d "$src_dir/bin" ] || {
        echo "[prebuild] ERROR: toolchain directory missing: $src_dir" >&2
        exit 1
    }

    echo "[prebuild] creating uncompressed toolchain tar from host rustup install..."
    tar -C "$HOME/.rustup/toolchains" -cf "$output_tar" "$toolchain_name"
    echo "[prebuild] rust toolchain tar built ($(du -h "$output_tar" | cut -f1))"

    install -m 0644 "$output_tar" "$overlay_dir/opt/rust-toolchain.tar"
}

require_x86_64
mkdir -p "$output_dir" "$overlay_dir/opt"
resize_rootfs
stage_source_archive
stage_source_metadata
stage_guest_resolver
stage_guest_runner
stage_guest_reboot_guard
stage_run_state
stage_rust_toolchain

echo "selfhost x86_64 overlay ready in $overlay_dir"
echo "rootfs=$rootfs"
echo "rootfs_size_mib=$rootfs_size_mib"
