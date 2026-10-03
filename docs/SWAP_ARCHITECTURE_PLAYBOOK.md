# 🛠️ Swap Architecture & Stability Playbook
**Document Version:** 1.0.0  
**Target System:** `z87-Linux` (Intel i7-4770K, 16GB RAM, RTX 2080 Ti 11GB)  
**Primary Objective:** Eliminate 2:00 AM compute-induced kernel deadlocks, preserve X11 canary signaling, and maximize I/O throughput via multi-tier striping and compressed memory paging.

---

## 1. The Architectural Context: Why ZFS on Linux Struggles with Swap

### Why does ZFS allow creating a swap zvol if it's prone to deadlock?
1. **Solaris Legacy vs. Linux Virtual Memory:**
   - ZFS was originally engineered by Sun Microsystems for **Solaris / OpenSolaris**. The Solaris kernel has a dedicated, non-pageable kernel memory subsystem (`kmem`) with strict static reservations for ZFS write operations.
   - When OpenZFS was ported to **Linux**, it had to interface with the Linux virtual memory manager (VMM). In Linux, out-of-tree/modular filesystem drivers rely on dynamic `kmalloc` / `vmalloc` allocations for transaction assembly.
2. **The Recursive Memory Deadlock:**
   - Under standard conditions, a ZFS zvol behaves like a normal block device.
   - However, during extreme memory starvation (e.g. 2:00 AM LoRA fine-tuning), Linux invokes `kswapd` to evict dirty pages to swap.
   - If that swap is a ZFS zvol (`/dev/zd0`), the write passes through the OpenZFS driver.
   - ZFS must allocate memory to build the **Transaction Group (`txg`)**, allocate **ZIO pipeline buffers**, and update **metadata trees**.
   - Because physical RAM is exhausted, ZFS blocks waiting for memory to free up.
   - Because `kswapd` is blocked waiting for the swap write to complete, no memory can be freed.
   - **Result:** Complete uninterruptible kernel freeze (`D` state), disk I/O stall, and eventual hardware watchdog reset.

### Can we keep ZFS Zvol Swap as a lower-priority secondary fallback?
- **Risk Assessment:** Setting `/dev/zd0` to `pri=1` (while primary swap is `pri=10`) means Linux will only touch `/dev/zd0` when primary swap is 100% full.
- **The Catch:** The moment the system actually fills primary swap and writes even a single megabyte into `/dev/zd0` under severe pressure, the exact same recursive deadlock triggers instantly.
- **Verdict:** Retaining `/dev/zd0` as a fallback leaves a hidden tripwire. The 8GB allocated to `rpool/swap` is far safer if returned to the general ZFS pool storage for datasets (`/home`, `/var`, etc.), with dedicated physical SSD space handling swap.

---

## 2. Hardware Topology & SSD Inventory

The host contains **three physical Intel SATA SSDs**:

| Drive | Model | Capacity | Current Filesystem / Role | Swap Suitability |
| :--- | :--- | :--- | :--- | :--- |
| **`sda`** | Intel Enterprise `SSDSC2BA800G4` | 800 GB | ZFS Root Pool (`rpool`), `bpool`, EFI, and **`sda5` (3.5 GB raw swap)** | ✅ Dedicated raw partition (`sda5`), direct block I/O |
| **`sde`** | Intel `SSDSA2M160G2GC` | 160 GB | **`btrfs` mounted at `/speedy`** (52.8 GB free) | ✅ Ideal for dedicated 8GB direct swapfile |
| **`sdd`** | Intel `SSDSC2BW240A4` | 240 GB | NTFS (`qwerty`) | ⏸️ Windows / Secondary storage |

---

## 3. Recommended Target Architecture: Multi-Tier Parallel Striped Swap

Instead of a single bottlenecked device, this architecture employs a **two-tier hierarchy**:

```
                              ┌───────────────────────────────────┐
                              │       Linux Virtual Memory        │
                              └─────────────────┬─────────────────┘
                                                │
                 ┌──────────────────────────────┴──────────────────────────────┐
                 ▼                                                             ▼
    [ TIER 1: In-RAM Compressed ]                                 [ TIER 2: Dual-SSD Parallel Striped ]
    zram-tools (zstd compression)                                 sda5 (3.5G SSD 1) + /speedy/swapfile (8.0G SSD 2)
    Priority: pri=100                                             Priority: pri=10 (Identical Priority)
    Capacity: 4.0 GB virtual                                      Capacity: 11.5 GB physical disk
    • 0ms disk latency                                            • Parallel SATA controller round-robin
    • Absorbs high-speed transient spikes                         • 2x throughput vs single disk
    • Compresses memory ~3:1 in RAM                               • Safe, pre-allocated block I/O (No ZFS deadlocks)
```

### Why Identical Priority Striping on Physical SSDs Works
When Linux sees two swap devices with the **exact same priority** (`pri=10`):
- It interleaves write pages across both `/dev/sda5` and `/speedy/swapfile` in parallel (RAID-0 style).
- Swap reads and writes utilize two independent SATA channels and controllers simultaneously.
- Combined disk swap capacity: **11.5 GB** (more than enough for the 4.9 GB peak recorded during 2:00 AM LoRA training).

---

## 4. Step-by-Step Implementation Plan

### Phase 1: Retire and Reclaim the ZFS Zvol Swap
1. Turn off active zvol swap:
   ```bash
   sudo swapoff /dev/zvol/rpool/swap
   ```
2. Destroy the zvol dataset to reclaim 8GB of disk space back to `rpool`:
   ```bash
   sudo zfs destroy rpool/swap
   ```
3. Remove the zvol line from `/etc/fstab`:
   ```bash
   sudo sed -i '\|/dev/zvol/rpool/swap|d' /etc/fstab
   ```

---

### Phase 2: Create Safe 8GB Swapfile on Second SSD (`/speedy` on `sde`)
Btrfs requires specific attributes (no copy-on-write, no compression) for swapfiles:

1. Create a zero-length file and set `no-COW`:
   ```bash
   sudo truncate -s 0 /speedy/swapfile
   sudo chattr +C /speedy/swapfile
   sudo btrfs property set /speedy/swapfile compression none
   ```
2. Pre-allocate 8 GB and set restrictive permissions:
   ```bash
   sudo fallocate -l 8G /speedy/swapfile
   sudo chmod 600 /speedy/swapfile
   ```
3. Format as swap space:
   ```bash
   sudo mkswap /speedy/swapfile
   ```

---

### Phase 3: Configure Tier 2 Striping in `/etc/fstab`
Update [`/etc/fstab`](file:///etc/fstab) to stripe across both physical SSDs at `pri=10`:

```ini
# --- TIER 2: PARALLEL DUAL-SSD STRIPED SWAP (11.5 GB TOTAL) ---
UUID=72edade8-5c91-48c7-9625-c49ecd3aed12 none swap sw,pri=10 0 0
/speedy/swapfile                           none swap sw,pri=10 0 0
```

Activate and verify:
```bash
sudo swapon -a
swapon --show
```

---

### Phase 4: Configure Tier 1 In-RAM Compression (`zram`)
1. Install `zram-tools`:
   ```bash
   sudo apt-get update -qq && sudo apt-get install -y zram-tools
   ```
2. Configure [`/etc/default/zramswap`](file:///etc/default/zramswap):
   ```ini
   # 4GB compressed RAM swap with zstd
   ALLOCATION=4096
   ALGO=zstd
   PRIORITY=100
   ```
3. Restart zram service:
   ```bash
   sudo systemctl restart zramswap
   ```

---

### Phase 5: Kernel Memory Subsystem Tuning (`/etc/sysctl.d/99-homelab-vm.conf`)
Ensure balanced page cache reclaiming and prevent dirty page backlogs:

```ini
# /etc/sysctl.d/99-homelab-vm.conf
# Encourage zram utilization while preventing aggressive thrashing
vm.swappiness = 60

# Keep filesystem metadata cached reasonably
vm.vfs_cache_pressure = 100

# Flush dirty pages to disk early to prevent I/O stampedes
vm.dirty_background_ratio = 5
vm.dirty_ratio = 10
```

Apply immediately:
```bash
sudo sysctl --system
```

---

## 5. Verification & Health Audit Checklist

Run the following checks to certify the new swap configuration:

- [ ] `swapon --show` confirms:
  - `/dev/zram0` active at `PRIO 100` (Tier 1)
  - `/dev/sda5` active at `PRIO 10` (Tier 2 Striped)
  - `/speedy/swapfile` active at `PRIO 10` (Tier 2 Striped)
  - `/dev/zd0` is completely gone.
- [ ] `zfs list -t volume` confirms `rpool/swap` no longer exists.
- [ ] `python3 /home/jallred/Dev_Lab/HomeLabAI/src/infra/reboot_reviewer.py` reports clean swap topology.
- [ ] Interactive X11 terminal session remains responsive and acts as a true canary without dragging the host kernel into unrecoverable hardware resets.
