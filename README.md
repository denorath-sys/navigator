<p align="center">
  <img src="theme/logo-wordmark.svg" alt="Navigator OS" width="560">
</p>

<p align="center">
  <em>An AI-native Linux desktop — Fedora Atomic, Hyprland, and an assistant wired into the system rather than bolted on top.</em>
</p>

---

Navigator is a Linux distribution that treats AI as a native part of the
operating system rather than a third-party application. Target audience:
developers, gamers and multimedia users on mid-to-high-end hardware.

The brand identity is a nautical/sky aesthetic built around the compass,
the lighthouse, the Orion constellation and the North Star (see
[`theme/palette.json`](theme/palette.json) and
[`theme/logo.svg`](theme/logo.svg)).

**New here?** [Introducing Navigator OS](docs/introducing-navigator.md) is the
short version — what it does, what it deliberately does not do yet, and the
screenshot that found two real bugs every textual test had missed.

## Architecture summary

| Layer | Choice |
|---|---|
| Base | Fedora Atomic (OSTree, monthly immutable image, [`image/Containerfile`](image/Containerfile)) |
| Compositor | [Hyprland](https://hyprland.org) (Wayland) — [`hyprland/`](hyprland/) |
| Shell | Custom shell built on [Quickshell](https://quickshell.outfoxxed.me/) (Qt6/QML) — [`shell/`](shell/) |
| AI stack | Hardware-driven model tier selection, MCP-based tool access, hybrid local↔cloud router — [`ai-stack/`](ai-stack/) |
| Theme | Brand colour palette + GTK/Qt theme — [`theme/`](theme/) |

Detailed architecture document: [`docs/architecture.md`](docs/architecture.md).

## Trying it

> **Status warning:** Navigator is in **Phase 4**. The desktop comes up, the
> shell runs, and every revision is boot-tested in a real VM in CI — but
> this is **not a daily-driver distribution**. The Ollama runtime now ships
> in the image (Layer 6), but **no model weights do** — which model belongs
> on your machine is your call. Until you run `ollama pull`, the assistant
> falls through to the cloud, which requires your own API key.
> Try it in a VM before putting it on your main machine.

**On an existing Fedora Atomic (bootc) system:**

```
sudo bootc switch ghcr.io/denorath-sys/navigator:latest
sudo systemctl reboot
```

If you don't like it, `sudo bootc rollback` returns you to the previous
deployment — rollback is lossless thanks to the immutable base. On older
systems without `bootc`, the equivalent is
`sudo rpm-ostree rebase ostree-unverified-registry:ghcr.io/denorath-sys/navigator:latest`.

**Trying it in a VM (recommended):** every
[`Build Disk Image & Boot Test`](../../actions/workflows/build-disk-and-boot-test.yml)
run produces a qcow2 disk image as an artifact named `navigator-disk-image`.
Download it and boot it with UEFI (OVMF) firmware — CI itself does exactly
that, so the QEMU step in
[`build-disk-and-boot-test.yml`](.github/workflows/build-disk-and-boot-test.yml)
doubles as a working command line.

**To run a model locally,** pull one — the Ollama runtime already ships in
the image (Layer 6) and its service is enabled, but no weights do:

```sh
ollama pull llama3.2:3b   # hardware-probe's recommendation for a "low" tier
```

Until then `model_ready` is false and the router routes to the cloud.

**To give the assistant cloud access,** put your own key in
`~/.config/navigator/env` (the file ships via `/etc/skel`, so image updates
never overwrite it):

```
ANTHROPIC_API_KEY=sk-ant-...
```

The assistant deliberately ignores the file unless it is `chmod 600`.
Details: [`ai-stack/cloud-bridge/`](ai-stack/cloud-bridge/).

## Roadmap

- **Phase 1 — Skeleton (done):** Repository structure, config/document
  drafts, CI pipeline definition. No large downloads were made locally; the
  Containerfile was verified by being built on GitHub Actions and pushed to
  `ghcr.io/denorath-sys/navigator` (base image: `ublue-os/base-main:43` +
  the `solopasha/hyprland` COPR). Quickshell was chosen as the shell
  technology.
- **Phase 2 — Local prototype (done):** The first implementation of
  `ai-stack/hardware-probe` was completed (Python, stdlib-only, 20 tests,
  verified against real hardware). Quickshell was added to
  `image/Containerfile` and the build was verified (`errornointernet/quickshell`
  COPR). The first QML shell files were written (`shell/shell.qml`,
  `Bar.qml`, `Theme.qml` and others — not yet tested at runtime at that
  point, see `shell/README.md`). The `ai-stack/local-runtime`
  orchestration/client layer was completed (Ollama REST client, tier→model
  recommendation, 16 tests). `ai-stack/mcp-tools` got its first MCP server
  (no official SDK, stdlib-only stdio JSON-RPC 2.0) and was then extended:
  sandboxed filesystem tools (`read_file` / `list_directory` / `write_file` /
  `delete_file` / `rename_file` — with path traversal blocking, overwrite
  protection for writes, a mandatory `confirm=true` for deletes, and
  sandbox checks on both source and destination for renames), the classic
  HTTP+SSE transport (`GET /sse` + `POST /messages`, in addition to stdio),
  mandatory Bearer token authentication for HTTP+SSE (automatic token
  generation, timing-attack-resistant comparison via `hmac.compare_digest` —
  running without authentication is never possible), and read-only Hyprland
  query tools (`list_windows` / `list_workspaces` / `active_window`,
  wrapping `hyprctl -j` — mocked plus graceful-failure tested at the time,
  since this Debian development machine has no real compositor; real window
  data was deferred to Phase 3) — 88 tests in total, verified end to end
  against real subprocesses and TCP sockets. `ai-stack/cloud-bridge` got its
  credential/client layer (Anthropic Claude API, stdlib-only raw HTTP, 16
  tests) and, with the owner's approval, **a real API key was wired up**
  (written to `.env.local`, excluded via `.gitignore` — never committed).
  `ai-stack/router` completed its decision layer **and** its integration
  with both `local-runtime` and `cloud-bridge` (it really invokes the
  relevant module as a subprocess according to the `route` decision, 27
  tests). With the owner's approval **Ollama was installed**
  (`curl -fsSL https://ollama.com/install.sh | sh`, ~1.37 GB) and the
  **`llama3.2:3b` model was pulled** (`ollama pull`, ~2 GB) — `route: "local"`
  genuinely works end to end on this machine and produces real text;
  **`route: "cloud"` also produces a real Claude API response** (tests that
  need credentials are designed to `skip` automatically when `.env.local` is
  absent or when running in CI). All five `ai-stack` modules are real: both
  the local and the cloud path work end to end on this machine.
  `hyprland/hyprland.conf` passed a static syntax review (a real compositor
  could not be run on this Debian development environment because Hyprland
  is not packaged there — see `hyprland/README.md`); no syntax errors were
  found, and one open question (`e+1`/`e-1` mouse-scroll workspace
  switching) was noted. Real runtime verification was deferred to Phase 3.
- **Phase 3 — Image build & test (first real boot test passed):**
  [`build-disk-and-boot-test.yml`](.github/workflows/build-disk-and-boot-test.yml)
  was added — it converts the Navigator image pushed to `ghcr.io` into a
  real qcow2 disk image with `bootc-image-builder`, then **actually boots**
  that disk image using the GitHub Actions runner's KVM (free
  `ubuntu-24.04` runners have had `/dev/kvm` since 2024) and verifies it
  over SSH. Three real CI failures were found and fixed (a wrong field name
  in the `customizations.user` schema; ublue-based images not declaring a
  default root filesystem inside the container, solved with `--rootfs btrfs`;
  and Ubuntu 24.04's `ovmf` package changing its file names). On the fourth
  run **a real VM really booted**: the disk build took 19 minutes, the VM
  became reachable over SSH, `/etc/os-release` confirmed the real image
  (`Fedora Linux 43.20260710.0`, `OSTREE_VERSION='43.20260710.0'`), and
  `systemctl is-system-running` returned `degraded` (the single failing
  unit being `mcelog.service`, which is expected in a virtual environment —
  it needs real hardware MCE registers that a VM does not have, and is
  harmless). It runs on manual trigger (`workflow_dispatch`) — unlike
  `build-image.yml` it does not run automatically on every push. This was
  the step where the static review of `hyprland.conf` and the Hyprland
  query tools in `mcp-tools` were verified for the first time in a real
  Fedora Atomic environment (partially — basic system boot, not the
  GUI/compositor). **Running a real Hyprland compositor session in this VM
  and testing the `mcp-tools` Hyprland tools against real window data** was
  investigated (technically feasible via QEMU `virtio-gpu-pci`, see
  `ai-stack/mcp-tools/README.md` under "Hyprland tools"), but the chain is
  long and each CI attempt takes ~20 minutes, so it was deliberately
  deferred to Phase 4/5 by the owner's decision.
- **Phase 4 — Completing the AI stack (in progress):** `ai-stack/assistant`
  was added — a CLI/REPL that combines `router`, `mcp-tools`, `local-runtime`
  and `cloud-bridge` into a single real conversation loop (as a first step
  that could genuinely be tested on this machine without waiting for the
  Quickshell UI). `--decide-only` (decide only, do not execute) was added to
  `router`, and `--converse` (multi-turn messages + tool use) to both
  `cloud-bridge` and `local-runtime`. **A real tool-use loop was verified end
  to end on both cloud and local:** for a complex hardware question, both
  Claude and the local `llama3.2:3b` really called the `hardware_tier` tool
  from `mcp-tools` and answered correctly using this machine's real data
  (6 cores, 15.4 GB RAM, no discrete GPU). **A security risk caught and
  fixed during real testing:** the local (3B) model spontaneously tried to
  call `write_file` with `overwrite=true` even on a harmless "just say
  hello" request — a genuine risk of violating the principle that "every
  system-modifying action requires explicit confirmation". The fix: write,
  delete and rename tools are no longer shown to the local model at all, it
  only has read-only access; and even if it hallucinates a call to one, a
  separate defence layer rejects it. The local model's remaining real
  reliability limits (occasional unnecessary tool calls, emitting raw JSON
  text) are documented rather than hidden (see
  `ai-stack/assistant/README.md`). **Conversation history/memory was added**:
  in memory in the REPL (cleared with `/reset`), and persistent even across
  separate processes via `--history-file`. **A "might this need tools?"
  signal was added to the router**: the complexity heuristic no longer looks
  only at word count but also at keywords relating to hardware, files and
  windows — short requests that nonetheless need tools (e.g. "how many CPU
  cores are there?") now automatically fall through to the more reliable
  cloud path on this machine (tier="low"), verified in real testing.
  **The real Hyprland compositor test was completed** (deferred from
  Phase 3): a `hyprland-test` job added to `build-disk-and-boot-test.yml`
  boots a real Navigator disk image in QEMU (`virtio-gpu-pci` +
  `-display vnc`, requiring no GPU/EGL on the host), really starts Hyprland,
  and calls the `mcp-tools` Hyprland query tools against a real compositor.
  Two real problems were found and fixed along the way: Hyprland's
  deliberate refusal to run as root (the `--i-am-really-stupid` flag was
  needed) and aquamarine's DRM backend trying to open a seat via `libseat`
  (an SSH session has no real seat; the missing `seatd` package was added to
  the image, and the test script starts seatd before Hyprland and sets
  `LIBSEAT_BACKEND=seatd`). Result: a real `hyprctl monitors` showed a
  "Virtual-1" (QEMU) monitor, and all three of `list_windows`,
  `list_workspaces` and `active_window` returned real JSON — not mocks (see
  `ai-stack/mcp-tools/README.md`, "Hyprland tools"). **`hyprland.conf` itself
  was also loaded by a real compositor in the same VM:** until then it had
  only passed a static syntax review (see `hyprland/README.md`); now CI
  really parses it and verifies via `hyprctl getoption` / `hyprctl binds`
  that five values differing from the defaults (border_size, rounding,
  blur:passes, resize_on_border, touchpad:natural_scroll) and the
  mainMod+RETURN→kitty binding are genuinely in effect, with no config
  errors found. **Quickshell itself was also run against real Hyprland in
  the same VM:** until then it had only passed a static `qmllint` review
  (see `shell/README.md`); now `qs -p shell.qml` really starts in CI and
  `Bar.qml` is mapped as a real layer-shell surface (verified with
  `hyprctl layers`, `namespace: quickshell`, at the real monitor width) —
  the first real end-to-end compositor+shell test. **`AssistantToggle` is
  now genuinely wired to `ai-stack/router`:** the new `AssistantPanel.qml`
  really invokes `python3 -m router` as a subprocess via
  `Quickshell.Io.Process`; the `IpcHandler` in `shell.qml` connects both the
  panel click and Hyprland's Super+Space (now `qs ipc call assistant toggle`,
  previously a placeholder `echo`) to the same panel. Verified end to end in
  CI — the real response was `[cloud] unavailable: credentials_not_configured`
  (CI has no Ollama or Claude credentials, so the router always falls
  through to cloud and cloud-bridge returns a graceful "unavailable" — not a
  mock, but a real end-to-end failure path). Two real problems were found
  and fixed along the way: `qs ipc call`'s `-p` flag being registered on the
  `ipc` subcommand (not on `call`), and `ai-stack/router`'s own dependency
  `ai-stack/hardware-probe` never having been copied into CI (see
  `shell/README.md`, "AssistantPanel — real ai-stack/router integration").
  **`ai-stack` is now a real layer of the image:** Layer 5 of
  `image/Containerfile` (a PLACEHOLDER until then) copies the six modules
  under `/usr/share/navigator/ai-stack/` and generates bytecode at build
  time with `compileall --invalidation-mode checked-hash` (because ostree
  normalises mtimes, timestamp-based `.pyc` files under a read-only `/usr`
  would be recompiled on every invocation — verified with a local
  `python3 -v` experiment, see `ai-stack/README.md`, "Installation path in
  the image"). This removed the scp + `rpm-ostree usroverlay` simulation in
  CI: `hyprland-test` now verifies the image's own contents with `/usr`
  read-only. **Layers 3 and 4 were also made real:** `theme/palette.json` →
  `/usr/share/navigator/theme/`, and `hyprland/hyprland.conf` →
  `/etc/skel/.config/hypr/` (new users start with this config, and their own
  copies are not overwritten by image updates). That also removed the `scp`
  simulation for `hyprland.conf` — the compositor test now loads the image's
  own file, and a separate step verifies that the two files in the image are
  byte-identical to the ones in the repository. On top of that, the
  **manually** maintained colour duplication between `palette.json` and
  `hyprland.conf` / `shell/Theme.qml` is now compared in CI (gradient stops
  plus angle, shadow colour, four `Theme.qml` constants); the check was
  proven to do real work by injecting a deliberate deviation.
  `theme/gtk` and `theme/qt` were deliberately not layered — they are still
  empty skeletons. **Layer 7 brought `shell/*.qml` into the image**
  (`/usr/share/navigator/shell/`, not `/etc/skel`, because it is program
  code — a user copy should not be frozen, and image updates should be able
  to update the shell). With that, the only thing copied from the runner to
  the VM in `build-disk-and-boot-test.yml` is the test script itself: every
  Navigator component under test comes from the image, and the colour sync
  check now reads all three files (`palette.json`, `hyprland.conf`,
  `Theme.qml`) from the image. **Hyprland now starts the desktop itself:**
  `exec-once` was added to `hyprland.conf` for the first time — the
  Navigator shell (from the path Layer 7 installs it to) and a polkit
  authorisation agent. waybar (it would conflict with our own panel),
  hyprpaper and hypridle (both requiring their own not-yet-written config)
  and systemd-managed services are deliberately left out; the reasoning is
  written down both in the config and in `hyprland/README.md`. CI verifies
  two new things: that every `exec-once` target is genuinely executable in
  the image (Hyprland silently swallows a wrong path, and no test would
  break), and that Quickshell now starts from the compositor's own
  `exec-once` rather than by hand. **The base moved from Fedora 43 to 44**
  (commit `f017ac5`). The base had been pinned to 43 because the
  `solopasha/hyprland` COPR packages would not depsolve on fc44; when
  diagnosed, this turned out not to be an ABI incompatibility but **a
  rebuild that had never happened**: that COPR's fc44 chroot had copied the
  packages from fc43 (`forked` status in COPR), so aquamarine still wanted
  `libdisplay-info.so.2` while F44 ships `.so.3`. The evidence: the same
  source built cleanly in the rawhide chroot, which carries libdisplay-info
  0.3. The solution was our own COPR: **`denorath/navigator-hyprland`**, 13
  packages genuinely built against fedora-44 from the same spec repository
  (`solopasha/hyprlandRPM`); it was confirmed in the repository metadata
  that `aquamarine` now requires `libdisplay-info.so.3`. Three real problems
  were found along the way: COPR passing the directory name to
  `.copr/Makefile` when the `spec` field is left empty (which also explains
  why solopasha's stable `hyprland` package had not been built at all since
  October 2025); the `glaze-static` build dependency being hidden in the
  spec's Lua block; and **F44 also moving from GCC 15 to 16** — WG21 P3953R3
  renamed `std::runtime_format` to `std::dynamic_format` and libstdc++ 16
  provides only the new name, so Hyprland 0.51.1 required a single source
  patch (`denorath-sys/hyprlandRPM`, branch `navigator-f44`; the spelling is
  selected from `__cpp_lib_format`, so the same source also builds on F43 —
  upstream removed these calls after 0.51.1, so the patch must be dropped on
  a version bump). **The assistant can now be configured on a real machine:**
  until then `cloud-bridge` read credentials only from the environment, and
  that was a path which did not work on the real image — `/usr` is read-only
  so no `.env.local` can be placed next to it, credentials cannot be baked
  into the image (the image is public), and because the chain that runs the
  panel (Hyprland `exec-once` → Quickshell → `Process` → router →
  cloud-bridge) inherits the environment the compositor was started in,
  there is no portable way to set a variable for a session opened through a
  greeter or TTY login. The solution is to read the credential **at the end
  of the chain**: `~/.config/navigator/env` (`cloud_bridge/config.py`),
  resolved relative to `HOME`, so it works even when Quickshell's
  environment is completely empty. The environment variable still takes
  precedence (so that the development flow and CI are not disrupted). Since
  the file carries a secret, it is **deliberately ignored** if it is
  readable beyond its owner (ssh's private-key behaviour), and the reason is
  distinguishable — `credentials_file_insecure` vs
  `credentials_not_configured`; the panel translates these slugs into
  sentences that mean something to a user for the first time
  (`explainReason()`, including the "chmod 600 ..." advice). Layer 4 now
  places a commented, **empty** template (0600) at
  `/etc/skel/.config/navigator/env`, so every new account finds it in place
  without having to guess the path. It was verified end to end with a real
  API key: with no `ANTHROPIC_*` in the environment at all, both the direct
  CLI and the `router → cloud-bridge` chain produced a real Claude response
  using only the credential resolved from the file, and it was genuinely
  refused once set to `chmod 644`. In CI (with no secret, using a fake key)
  the resolution inside the image, the permission refusal and the
  template's mode are verified; the check was shown not to be vacuously
  green by injecting three deliberate deviations — one of which caught a
  real defect: with the assertions in the wrong order, if the refusal logic
  broke, CI would really reach out to the API with the fake key. The order
  was fixed. `solopasha/hyprland` is **deliberately not enabled** in the
  Containerfile: if both were enabled, their copied `0.51.1-3.fc43` would
  beat our `0.51.1-1.fc44` (rpm compares release first) and the image would
  silently fall back to broken packages; all eight of the other packages
  Layer 1 needs are available in the official F44 repository. Verified end
  to end: the image build passed and `build-disk-and-boot-test.yml` reported
  `Fedora Linux 44.20260801.0` in the VM, Hyprland came up, its own
  `exec-once` started Quickshell from the image path and `hyprctl layers`
  showed a real layer-shell surface (`namespace: quickshell`), and the
  AssistantPanel → `ai-stack/router` chain responded. Layer 2's choice of
  `dnf5 install` was deliberately left alone: its rationale (not being able
  to upgrade the old Qt in the base image) appears to have disappeared on
  F44 — the CI log shows `qt6-qtbase-6.11.1` installed from `updates`
  without an upgrade — but returning to `rpm-ostree install` should be a
  separate experiment; two variables were not changed in the same build as
  the F44 migration. **`WorkspaceIndicator` was wired to real Hyprland
  data:** the indicator, long a static 1-10 row of pills, now uses
  `Quickshell.Hyprland`'s `Hyprland.workspaces` model, shows
  `focused`/`active` states, and switches workspace via `activate()` when
  clicked; there is NO polling — Quickshell listens to the compositor's
  event socket (socket2) itself. The visible consequence: only workspaces
  that actually EXIST are listed (Hyprland does not report empty ones). CI
  verifies two separate things: whether the set and the focus the shell sees
  match `hyprctl`'s own report exactly, and whether the shell notices a real
  change in the compositor (`dispatch workspace 3`) on its own — a static
  placeholder or a one-shot read cannot pass the second; the comparison
  logic was exercised locally against three deliberate deviations without
  spending CI. **Visual correctness testing began:** every verification up
  to this point had been textual (`hyprctl` output, IPC responses, process
  states) — whether the desktop actually LOOKED right had never been
  measured. The boot test now captures the screen's current contents:
  `screendump` via **QEMU's own HMP monitor**, raw PPM straight to the host.
  No VNC client, no screenshot tool inside the guest and no extra package in
  the image are NEEDED, and because the capture is independent of the guest
  it is exactly what the user sees. Two stdlib-only scripts
  (`.github/scripts/`, kept in the repository rather than embedded in the
  workflow so they can be exercised locally) take the image, analyse it and
  produce a dependency-free PNG uploaded as an artifact: the screenshot can
  now really be looked at. Only two things are ASSERTED this round (a valid
  PPM, and the image not being a single colour — a flat black screen must
  not stay silently green); bar height, brand-colour pixel counts and row
  brightness are DIAGNOSTICS for now, and will not be promoted to assertions
  before the real numbers have been read. **The first screenshot paid for
  itself immediately:** it confirmed that the brand teal renders exactly as
  specified on screen (1904 pixels) and that the AssistantPanel's credential
  message really appears — but the same image also revealed two real
  problems that had silently passed EVERY textual test until then: (1)
  Hyprland's red config-error banner at the top of the screen —
  `gestures:workspace_swipe` had been removed in 0.51 and the config was
  still using it; (2) the desktop still showing the stock Hyprland
  wallpaper, with no Navigator wallpaper of its own. The first was fixed
  (`gesture = 3, horizontal, workspace`) and the real lesson was written
  into CI: the old `grep "config error" hyprland.log` check **was giving
  false assurance** (it printed "(none)"), and was replaced by a
  `hyprctl configerrors` assertion that asks the compositor directly.
  **The desktop looks like Navigator for the first time:** both gaps the
  screenshot revealed were closed. (1) `hyprland-qtutils` was missing, and
  Hyprland was showing a yellow info banner on the desktop that covered the
  right-hand side of the top panel; the package does not exist in Fedora at
  all (not even in dist-git), so it was added to our own COPR together with
  its runtime dependency `hyprland-qt-support` and built against fedora-44.
  (2) The desktop was showing the stock Hyprland wallpaper; `theme/wallpaper.png`
  now carries Navigator's brand image and went into `exec-once` along with a
  `hyprpaper` config.
  **The verification method changed once in the process, and that was
  instructive:** the first version asked "is the desktop dark?" (stock 85.3,
  the procedural wallpaper of the time 21.6). When the real brand image
  arrived, that measure collapsed — because of the bright wave in its
  middle, the same band's luma is 73.0, i.e. adjacent to stock's 85.3.
  Brightness was measuring only a summary of the wallpaper, not its
  IDENTITY. It was replaced by a measure comparing the screenshot to the
  reference image **block by block** (24x15 blocks, the median of the
  differences — the median being robust against windows covering the screen;
  hyprpaper's "cover" cropping is accounted for). The threshold again comes
  from measurement: the same wallpaper 0.1, a wrong Navigator wallpaper
  37.9, stock Hyprland 68.7 → threshold 15, with over a hundredfold margin
  on both sides. Remaining: real mouse clicks (input injection).
  **Layer 6 (Ollama) is no longer a placeholder:** the runtime now ships in
  the image, from the official Fedora repository (no COPR needed). It is not
  cheap — measured from the real build, the image went from **3.26 GB to
  5.62 GB compressed (+72%)**, in a single 2364 MB layer. Most of that is
  rocblas, ROCm's GPU kernels, which arrive as a hard dependency (ollama
  requires `libhipblas.so.3`) and cannot be excluded without breaking the
  package. The alternatives were measured and are worse: upstream's own
  tarballs for the same release are 1047 MB (rocm) and 1421 MB (default, now
  bundling CUDA). Model weights are still deliberately not shipped. A
  prediction of "+345 MB" was made before the build and was wrong by seven
  times, because package metadata reports the compressed *download* rather
  than the layer — the correction is kept in the Containerfile as a lesson.
- **Phase 5 — User testing & release preparation:** installation tests on
  real hardware, documentation, first community release.

## Development constraints (why some things are the way they are)

This project is developed over a metered/roaming connection. That directly
explains many decisions in the repository, so it is not hidden:

- Downloads over 200 MB (packages, ISOs, model files, container images) are
  not made without approval. This is why **model weights are not shipped in
  the image** — the Ollama runtime itself is layered in (Layer 6), since that
  download happens on GitHub's runners rather than on the maintainer's
  connection, but a model is the user's choice and another ~2 GB.
- Heavy operations (`rpm-ostree compose`, real ISO builds, model pulls) are
  not run locally; the necessary scripts, configs and CI pipeline files are
  written instead.
- Real build and test work runs on GitHub Actions
  ([`build-image.yml`](.github/workflows/build-image.yml),
  [`build-disk-and-boot-test.yml`](.github/workflows/build-disk-and-boot-test.yml)).
  This has a side benefit: **every claim has a real run link behind it that
  verifies it.** The run numbers you see in the module READMEs in this
  repository are not decoration, they are measured output.

## How claims in this repository are verified

This is the project's one strong convention, and the thing most worth
knowing before reading the code: **nothing is presented as working unless it
was measured.** Module READMEs cite the CI run that proves each claim, and
limitations are recorded in the same place as the successes.

Two habits follow from that, and both have repeatedly paid off:

- When a behaviour is not a documented guarantee, it is first measured as a
  **diagnostic that cannot fail the job**, and only promoted to an assertion
  once the real answer is known. Writing the assertion first — from memory,
  before measuring — is the mistake this repository has made most often.
- Checks are proven not to be vacuously green by deliberately injecting a
  breakage and confirming the check goes red. This is what caught a
  config-error check that was actively reporting "none" while errors existed.

## Contributing

This is a one-person hobby project. Documentation and code comments are in
English; commit messages before August 2026 are in Turkish, which is why the
history reads bilingually — the history was deliberately not rewritten, so
that the commit SHAs cited throughout the documentation remain valid.

1. Check existing issues and PRs before opening a new one.
2. For significant architectural changes, open a discussion/RFC first.
3. A PR is enough for config and documentation changes. Code contributions
   are accepted; note that the `ai-stack/` modules follow a **stdlib-only**
   rule (no third-party dependencies), so a PR that breaks it should be
   discussed first.
4. Explain *why* a change was made in the commit message.
5. **No claim lands in this repository without a measurement behind it.** If
   you say something works, include the test or the CI run link; writing
   "not measured" is entirely acceptable.

## License

[GPL-3.0](LICENSE)
