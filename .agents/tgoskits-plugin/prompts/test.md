---
description: Run builds and tests in the project Docker CI image
argument-hint: "[quick|full|fmt|clippy|starry|arceos|axvisor] [arch]"
---

# Run CI checks in the Docker container

Arguments: `${1:-quick}` `${2:-all}`

## Dispatch

| Invocation | Action |
|---|---|
| `/test` | Quick checks (fmt + clippy + sync-lint) |
| `/test quick` | Quick checks |
| `/test full` | Full CI matrix (all OSes, all architectures) |
| `/test fmt` | `cargo fmt --all -- --check` |
| `/test clippy` | `cargo xtask clippy` |
| `/test starry aarch64` | StarryOS QEMU tests for aarch64 |
| `/test arceos riscv64` | ArceOS QEMU tests for riscv64 |
| `/test axvisor` | Axvisor QEMU tests for all three architectures |
| `/test starry all` | StarryOS QEMU tests for all four architectures |

Plugin root: `.agents/tgoskits-plugin` (override with `TGOSKITS_PLUGIN_ROOT`).

## Steps

1. Map the invocation to a command:
   - `fmt`: `docker run --rm -v "$PWD:/workspace" -w /workspace tgoskits-ci bash -c "cargo fmt --all -- --check"`
   - `clippy`: `docker run --rm -v "$PWD:/workspace" -w /workspace tgoskits-ci bash -c "cargo xtask clippy"`
   - `quick`: `bash .agents/tgoskits-plugin/scripts/local-ci.sh quick`
   - `full`: `bash .agents/tgoskits-plugin/scripts/local-ci.sh full`
   - `<os> <arch>`: `bash .agents/tgoskits-plugin/scripts/local-ci.sh test <os> <arch>`
   - `<os> all`: run the `test` mode for each supported architecture of that OS.
2. Verify Docker first. If the daemon is unreachable, stop and report; do not fall
   back to running tests on the host.
3. Run `quick` once when no image exists yet, so the base image is built.
4. Execute the mapped command and capture stdout and stderr.
5. `local-ci.sh` writes the outcome to `.agents/tgoskits-plugin/cache/last-ci-result.json`.
6. Report: "All checks passed." or list each failing command with its error output.

Do not relax or skip a failing check to make the run green.
