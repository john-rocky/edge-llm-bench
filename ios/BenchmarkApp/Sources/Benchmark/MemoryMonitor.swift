import Foundation
import Darwin
#if canImport(Metal)
import Metal
#endif

/// Process-memory sampling via Mach `task_info`, the VM region query and Metal.
///
/// A run's memory sits in up to three places, and which ones depends on the runtime:
///
/// 1. **`phys_footprint`** (`TASK_VM_INFO`): the byte count the OS charges the
///    process, the figure iOS enforces its per-process limit (jetsam) against
///    and Activity Monitor's "Memory" column. It counts dirty, compressed and
///    IOKit memory, which on Apple silicon includes the Metal buffers a runtime
///    allocates (MLX keeps its weights there). It does not count clean
///    file-backed pages: a model the runtime memory-maps and never writes.
/// 2. **Mapped file pages in the process's page table** (`external`, the
///    file-backed part of `resident_size`): where a memory-mapped model sits once
///    the CPU has read it (llama.cpp's GGUF, LiteRT-LM's weight cache on the CPU
///    backend).
/// 3. **Memory the GPU wraps without a copy** (`newBufferWithBytesNoCopy`), which
///    the OS charges to nobody: a mapped model file (LiteRT-LM's GPU weight cache,
///    llama.cpp's GGUF) or anonymous memory the runtime allocates (llama.cpp's KV
///    cache and compute buffers on Apple silicon). Measured as the pages in RAM of
///    the VM objects behind the regions the GPU wraps (`measureOverlap(metalBeyondLedger:)`).
///
/// Place 3 overlaps the other two wherever the CPU has touched wrapped memory too:
/// a file mapped shared keeps the pages the CPU read in the page table (place 2);
/// anonymous memory, and a file mapped private (copied into anonymous memory at the
/// GPU's first read), keep the pages the CPU touched in `phys_footprint` (place 1).
/// Pages only the GPU has touched are in place 3 alone. The overlaps are measured,
/// not assumed: they are the wrapped regions' pages in the page table (the region
/// query in footprint mode answers from the page table), so the total adds only the
/// wrapped pages outside it.
///
/// The wrap shows in the region query: the region turns "true shared" and its VM
/// object gains a reference (a shared file mapping 2 -> 3, anonymous memory 1 -> 2;
/// a private file mapping's top object turns anonymous and true shared at the GPU's
/// first read). A runtime may wrap only part of a mapping (llama.cpp leaves the
/// tensors the CPU computes out of its GPU buffers); counting whole VM objects needs
/// no knowledge of the parts, because whatever of the region is in the page table is
/// subtracted again.
///
/// Metal's own figure (`MTLDevice.currentAllocatedSize`) beyond the kernel ledger's
/// graphics and neural part of `phys_footprint` is LiteRT's estimate of place 3
/// ("mapped weights") and is kept beside it. It counts a wrapped buffer at its length,
/// touched or not, and allocated resources before their pages are charged, and it
/// falls short by any graphics memory the ledger holds outside Metal's figure.
///
/// `read()` takes one `TASK_VM_INFO` reading and Metal's figure and derives the
/// quantities of LiteRT's own memory profiler (google-ai-edge/LiteRT,
/// `litert/core/util/memory_profiling/`: `host_memory_apple.cc`,
/// `accelerator_memory_apple.mm`, `memory_snapshot.h`), under the same names:
///
/// - host resident = `resident_size`; host attributed = `phys_footprint`;
/// - accelerator attributed = the ledger's graphics + neural parts of
///   `phys_footprint`, compressed pages included;
/// - accelerator present = the ledger's graphics + neural pages in RAM, plus
///   what Metal has allocated beyond the whole ledger ("mapped weights");
/// - resident in RAM = host resident + accelerator present, attributed by OS =
///   `phys_footprint` (their `MemorySnapshot`). Resident in RAM counts a page
///   twice when it is in the page table and also accelerator memory.
///
/// and `totalBytes`, which counts each page once: place 1 + place 2 + place 3 −
/// the two overlaps (`methodology/memory.md` "Three places").
public enum MemoryMonitor {
    /// Current physical footprint in megabytes — the jetsam-relevant figure.
    /// Returns 0 on failure.
    public static func footprintMB() -> Double {
        guard let r = read(includeMetal: false) else { return 0 }
        return Double(r.footprintBytes) / mib
    }

    /// Resident size (RSS) in megabytes. Returns 0 on failure.
    public static func residentMB() -> Double {
        guard let r = read(includeMetal: false) else { return 0 }
        return Double(r.residentBytes) / mib
    }

    static let mib = 1024.0 * 1024.0

    /// One reading: every counter of one `task_info(TASK_VM_INFO)` call, and Metal's
    /// figure read right after it.
    public struct Reading: Sendable {
        /// `resident_size`: pages in the process's page table.
        public var residentBytes: UInt64 = 0
        /// `phys_footprint` (place 1).
        public var footprintBytes: UInt64 = 0
        /// `internal`: anonymous pages in the page table.
        public var internalBytes: UInt64 = 0
        /// `external`: file-backed pages in the page table (place 2).
        public var externalBytes: UInt64 = 0
        /// `compressed`: the process's pages held compressed.
        public var compressedBytes: UInt64 = 0
        /// Whether the kernel filled the per-tag ledger (`task_vm_info` revision 3 on);
        /// without it the ledger fields read zero and mean "unknown".
        public var hasLedger = false
        /// `ledger_tag_graphics_footprint` (pages in RAM) and `_compressed`.
        public var graphicsBytes: UInt64 = 0
        public var graphicsCompressedBytes: UInt64 = 0
        /// `ledger_tag_neural_footprint` (pages in RAM) and `_compressed`.
        public var neuralBytes: UInt64 = 0
        public var neuralCompressedBytes: UInt64 = 0
        /// `ledger_tag_graphics_nofootprint` / `ledger_tag_neural_nofootprint` (+ their
        /// compressed parts): GPU / Neural Engine memory tagged to the process but kept
        /// out of `phys_footprint`. Not in LiteRT's figures; recorded to see it.
        public var graphicsNoFootprintBytes: UInt64 = 0
        public var neuralNoFootprintBytes: UInt64 = 0
        /// Sum of `MTLDevice.currentAllocatedSize` over the process's Metal devices
        /// (macOS: every device, iOS: the default one); nil without a device.
        public var metalAllocatedBytes: UInt64?
        /// The GPU-wrapped regions as `measureOverlap(metalBeyondLedger:)` last measured them (the
        /// sampler fills it in; `read()` leaves it empty); nil when it was needed and
        /// could not be measured.
        public var overlap: Overlap? = Overlap()

        public init() {}

        /// The part of `phys_footprint` the kernel charges to the GPU and the Neural
        /// Engine, in RAM or compressed (LiteRT: accelerator `attributed_bytes`).
        public var acceleratorAttributedBytes: UInt64 {
            graphicsBytes &+ graphicsCompressedBytes &+ neuralBytes &+ neuralCompressedBytes
        }

        /// What Metal has allocated beyond the whole ledger (LiteRT's estimate of place
        /// 3: the "mapped weights" breakdown entry). Without the ledger all of Metal's
        /// figure lands here, as in LiteRT.
        public var mappedWeightsBytes: UInt64 {
            guard let metal = metalAllocatedBytes else { return 0 }
            let charged = acceleratorAttributedBytes
            return metal > charged ? metal - charged : 0
        }

        /// Accelerator memory present now: the ledger's pages in RAM plus the mapped
        /// weights (LiteRT: accelerator `total_bytes`).
        public var acceleratorPresentBytes: UInt64 {
            graphicsBytes &+ neuralBytes &+ mappedWeightsBytes
        }

        /// LiteRT's `MemorySnapshot.resident_in_ram` total: host resident + accelerator
        /// present (their CPU part is the whole host resident figure).
        public var residentInRAMBytes: UInt64 {
            residentBytes &+ acceleratorPresentBytes
        }

        /// The two overlaps, place 3's with place 2 and with place 1, together. Nil when
        /// the wrapped regions could not be measured.
        public var overlapCountedBytes: UInt64? {
            overlap.map { $0.externalBytes &+ $0.footprintBytes }
        }

        /// Every page once: `phys_footprint` + `external` + place 3 − its two overlaps,
        /// which is the wrapped pages outside the page table (`Overlap.gpuOnlyBytes`).
        /// Nil when the wrapped regions could not be measured.
        public var totalBytes: UInt64? {
            guard let o = overlap else { return nil }
            return footprintBytes &+ externalBytes &+ o.gpuOnlyBytes
        }
    }

    /// The GPU-wrapped regions at one instant (`measureOverlap(metalBeyondLedger:)`), in bytes.
    public struct Overlap: Sendable {
        /// Place 3: the pages in RAM of the VM objects behind the wrapped regions.
        public var residentBytes: UInt64 = 0
        /// The part of it in the page table through a shared file mapping: in place 2.
        public var externalBytes: UInt64 = 0
        /// The part of it in the page table through anonymous memory or a private file
        /// mapping: anonymous pages, in place 1.
        public var footprintBytes: UInt64 = 0
        /// The rest, in neither the page table nor the footprint: the pages only the GPU
        /// holds, which the total adds.
        public var gpuOnlyBytes: UInt64 = 0
        /// The wrapped regions' sizes.
        public var locatedBytes: UInt64 = 0

        public init() {}
    }

    /// Reads every counter. `includeMetal: false` skips Metal's figure (the two
    /// single-number helpers above). Nil when `task_info` fails. The overlap is left
    /// at 0; `MemorySampler` measures it when places 2 and 3 are both non-zero.
    public static func read(includeMetal: Bool = true) -> Reading? {
        var info = task_vm_info_data_t()
        var count = mach_msg_type_number_t(
            MemoryLayout<task_vm_info_data_t>.size / MemoryLayout<integer_t>.size
        )
        let result = withUnsafeMutablePointer(to: &info) { ptr -> kern_return_t in
            ptr.withMemoryRebound(to: integer_t.self, capacity: Int(count)) { reboundPtr in
                task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), reboundPtr, &count)
            }
        }
        guard result == KERN_SUCCESS else { return nil }

        var r = Reading()
        r.residentBytes = info.resident_size
        r.footprintBytes = info.phys_footprint
        r.internalBytes = info.internal
        r.externalBytes = info.external
        r.compressedBytes = info.compressed
        // The per-tag ledger arrived with revision 3 of the struct; an older kernel
        // fills fewer words and leaves it zero, which would read as "no GPU memory".
        if Int(count) * MemoryLayout<integer_t>.size >= ledgerEndOffset {
            r.hasLedger = true
            r.graphicsBytes = nonNegative(info.ledger_tag_graphics_footprint)
            r.graphicsCompressedBytes = nonNegative(info.ledger_tag_graphics_footprint_compressed)
            r.neuralBytes = nonNegative(info.ledger_tag_neural_footprint)
            r.neuralCompressedBytes = nonNegative(info.ledger_tag_neural_footprint_compressed)
            r.graphicsNoFootprintBytes = nonNegative(info.ledger_tag_graphics_nofootprint)
                &+ nonNegative(info.ledger_tag_graphics_nofootprint_compressed)
            r.neuralNoFootprintBytes = nonNegative(info.ledger_tag_neural_nofootprint)
                &+ nonNegative(info.ledger_tag_neural_nofootprint_compressed)
        }
        if includeMetal {
            r.metalAllocatedBytes = metalAllocatedBytes()
        }
        return r
    }

    /// Byte offset of the first field after the revision-3 ledger block.
    private static let ledgerEndOffset: Int =
        MemoryLayout<task_vm_info_data_t>.offset(of: \task_vm_info_data_t.limit_bytes_remaining)
        ?? MemoryLayout<task_vm_info_data_t>.size

    /// The ledger fields are signed; a negative reading is zero, not a wrapped value.
    private static func nonNegative(_ bytes: Int64) -> UInt64 {
        bytes > 0 ? UInt64(bytes) : 0
    }

    #if canImport(Metal)
    /// The process's Metal devices, enumerated once (creating the device objects if
    /// nothing else in the process has). macOS: every device, since the figure is per
    /// process and a device this process does not use reads zero; iOS: the default one.
    nonisolated(unsafe) private static let metalDevices: [any MTLDevice] = {
        #if os(macOS)
        let all = MTLCopyAllDevices()
        if !all.isEmpty { return all }
        #endif
        if let device = MTLCreateSystemDefaultDevice() { return [device] }
        return []
    }()

    static func metalAllocatedBytes() -> UInt64? {
        let devices = metalDevices
        guard !devices.isEmpty else { return nil }
        return devices.reduce(UInt64(0)) { $0 &+ UInt64($1.currentAllocatedSize) }
    }
    #else
    static func metalAllocatedBytes() -> UInt64? { nil }
    #endif

    // MARK: - The overlap of places 2 and 3

    /// One VM region as the short region query describes it.
    struct Region {
        var address: UInt64
        var size: UInt64
        var info: vm_region_submap_short_info_data_64_t
    }

    /// Every top-level region of the process (shared submaps not entered).
    static func regions() -> [Region] {
        var out: [Region] = []
        var address: UInt64 = 0
        while true {
            var size: UInt64 = 0
            var info = vm_region_submap_short_info_data_64_t()
            guard regionQuery(&address, &size, &info) else { break }
            out.append(Region(address: address, size: size, info: info))
            address &+= size
        }
        return out
    }

    /// What a GPU buffer made on a region without a copy (`newBufferWithBytesNoCopy`)
    /// does to the region query (measured on an Apple M4 Max, macOS 27, 256 MB test
    /// buffers): a file mapped shared turns "true shared" and its VM object gains a third
    /// reference (the file's cache, the mapping, the GPU); anonymous memory turns true
    /// shared with a second reference; a file mapped private keeps its short-query
    /// look (copy-on-write, the file's pager) but at the GPU's first read its pages move
    /// into an anonymous VM object, true shared, which the full query reports. Memory
    /// Metal allocates itself carries the IOAccelerator / IOKit / IOSurface tags and is
    /// charged to the ledger instead. A file shared by plain mappings of other
    /// processes is "shared", not "true shared", and is left out.
    enum Wrap { case sharedFile, anonymous, privateFile }

    /// The kind of wrap the short query shows, or `.privateFile` for a private file
    /// mapping that may be wrapped (the full query decides).
    static func wrapCandidate(_ info: vm_region_submap_short_info_data_64_t) -> Wrap? {
        guard info.is_submap == 0 else { return nil }
        switch Int32(info.user_tag) {
        case VM_MEMORY_IOACCELERATOR, VM_MEMORY_IOKIT, VM_MEMORY_IOSURFACE: return nil
        default: break
        }
        if info.external_pager != 0 {
            // inheritance 0 = VM_INHERIT_SHARE: mapped with MAP_SHARED.
            if info.inheritance == 0 {
                return info.share_mode == SM_TRUESHARED && info.ref_count >= 3 ? .sharedFile : nil
            }
            return info.share_mode == SM_COW && info.ref_count >= 3 ? .privateFile : nil
        }
        return info.share_mode == SM_TRUESHARED && info.ref_count >= 2 ? .anonymous : nil
    }

    /// Finds the GPU-wrapped regions and measures them: the pages of their VM objects in
    /// RAM (place 3, the full region query in normal mode), the part of those in the page
    /// table (footprint mode; the overlaps), and the regions' sizes. Nil when the
    /// page-table query is refused (`vm.self_region_footprint`). Costs one short query per
    /// region and two page walks of each wrapped region (measured on an M4 Max: 0.7 ms for
    /// 620 regions, 0.7-0.8 ms per 512 MB walked).
    ///
    /// Confirming a private file mapping takes the full query, which walks every page of
    /// the mapping (a model file mapped in pieces: 10-38 ms for 3.7 GB), so it runs only while
    /// Metal's figure beyond the ledger (`metalBeyondLedger`) exceeds the sizes of the
    /// regions already found by 32 MiB: memory the GPU holds that is not located yet.
    static func measureOverlap(metalBeyondLedger: UInt64) -> Overlap? {
        var found: [(region: Region, kind: Wrap, object: UInt64)] = []
        var privateCandidates: [Region] = []
        let page = UInt64(getpagesize())
        for region in regions() {
            guard let kind = wrapCandidate(region.info) else { continue }
            if kind == .privateFile {
                privateCandidates.append(region)
                continue
            }
            guard let full = fullInfo(at: region.address) else { continue }
            found.append((region, kind, UInt64(full.pages_resident) * page))
        }
        let located = found.reduce(UInt64(0)) { $0 &+ $1.region.size }
        if metalBeyondLedger > located &+ privateSearchMargin {
            for region in privateCandidates {
                guard let full = fullInfo(at: region.address),
                      full.share_mode == SM_TRUESHARED, full.external_pager == 0 else { continue }
                found.append((region, .privateFile, UInt64(full.pages_resident) * page))
            }
        }
        let wrapped = found
        var o = Overlap()
        if wrapped.isEmpty { return o }
        guard setFootprintMode(true) else { return nil }
        defer { _ = setFootprintMode(false) }
        for w in wrapped {
            guard let p = pages(at: w.region.address) else { return nil }
            let inTable = min(p.resident, w.object)
            o.locatedBytes &+= w.region.size
            o.residentBytes &+= w.object
            switch w.kind {
            case .sharedFile: o.externalBytes &+= inTable
            case .anonymous, .privateFile: o.footprintBytes &+= inTable
            }
            o.gpuOnlyBytes &+= w.object - inTable
        }
        return o
    }

    private static let privateSearchMargin: UInt64 = 32 * 1024 * 1024

    /// The full region query (normal or footprint mode, whichever is on) of the region
    /// that starts at `address`.
    private static func fullInfo(at address: UInt64) -> vm_region_submap_info_data_64_t? {
        var a = address
        var size: UInt64 = 0
        var info = vm_region_submap_info_data_64_t()
        guard regionQueryFull(&a, &size, &info), a == address else { return nil }
        return info
    }

    /// Pages of the region at `address` from the full region query, in bytes: resident
    /// (normal mode: the pages of its VM object in RAM; footprint mode: the pages in this
    /// process's page table), dirtied, and compressed or swapped out.
    static func pages(at address: UInt64) -> (resident: UInt64, dirty: UInt64, compressed: UInt64)? {
        var a = address
        var size: UInt64 = 0
        var info = vm_region_submap_info_data_64_t()
        guard regionQueryFull(&a, &size, &info), a == address else { return nil }
        let page = UInt64(getpagesize())
        return (UInt64(info.pages_resident) * page, UInt64(info.pages_dirtied) * page,
                UInt64(info.pages_swapped_out) * page)
    }

    /// Footprint mode for this process's own region queries (`vm.self_region_footprint`,
    /// the switch `vmmap` and `footprint` use): on, the full region query counts the
    /// pages of the process's page table.
    static func setFootprintMode(_ on: Bool) -> Bool {
        var value: Int32 = on ? 1 : 0
        return sysctlbyname("vm.self_region_footprint", nil, nil, &value, MemoryLayout<Int32>.size) == 0
    }

    private static func regionQuery(
        _ address: inout UInt64, _ size: inout UInt64, _ info: inout vm_region_submap_short_info_data_64_t
    ) -> Bool {
        var depth: natural_t = 0
        var count = mach_msg_type_number_t(
            MemoryLayout<vm_region_submap_short_info_data_64_t>.size / MemoryLayout<natural_t>.size)
        return withUnsafeMutablePointer(to: &info) { p in
            p.withMemoryRebound(to: Int32.self, capacity: Int(count)) { infoPtr in
                recurse(&address, &size, &depth, infoPtr, &count)
            }
        }
    }

    private static func regionQueryFull(
        _ address: inout UInt64, _ size: inout UInt64, _ info: inout vm_region_submap_info_data_64_t
    ) -> Bool {
        var depth: natural_t = 0
        var count = mach_msg_type_number_t(
            MemoryLayout<vm_region_submap_info_data_64_t>.size / MemoryLayout<natural_t>.size)
        return withUnsafeMutablePointer(to: &info) { p in
            p.withMemoryRebound(to: Int32.self, capacity: Int(count)) { infoPtr in
                recurse(&address, &size, &depth, infoPtr, &count)
            }
        }
    }

    private static func recurse(
        _ address: inout UInt64, _ size: inout UInt64, _ depth: inout natural_t,
        _ info: UnsafeMutablePointer<Int32>, _ count: inout mach_msg_type_number_t
    ) -> Bool {
        #if os(macOS)
        var a = mach_vm_address_t(address)
        var s = mach_vm_size_t(0)
        let kr = mach_vm_region_recurse(mach_task_self_, &a, &s, &depth, info, &count)
        #else
        var a = vm_address_t(address)
        var s = vm_size_t(0)
        let kr = vm_region_recurse_64(mach_task_self_, &a, &s, &depth, info, &count)
        #endif
        guard kr == KERN_SUCCESS else { return false }
        address = UInt64(a)
        size = UInt64(s)
        return true
    }
}

/// One sampler window's memory in the terms of `MemoryMonitor.Reading`, in MiB
/// (bytes / 2^20): each series' peak and median over the window, and the whole
/// reading at the sample where the total peaked (its parts add up to it).
public struct MemoryAccounting: Sendable {
    /// Names the definition the fields follow (`methodology/memory.md` "Three places").
    public static let basis = "apple-vm-wrapped-pages-v1"

    public var peakExternalMB: Double
    public var medianExternalMB: Double
    public var peakAcceleratorPresentMB: Double?
    public var medianAcceleratorPresentMB: Double?
    public var peakAcceleratorAttributedMB: Double?
    public var medianAcceleratorAttributedMB: Double?
    public var peakResidentInRAMMB: Double?
    public var medianResidentInRAMMB: Double?
    /// Nil when some sample needed the overlap and it could not be measured.
    public var peakTotalMB: Double?
    public var medianTotalMB: Double?
    public var atTotalPeak: MemoryBreakdown?
    /// The overlap queries the window ran and the time they took.
    public var overlapQueries: Int
    public var overlapQueryMS: Double
}

/// One reading, in MiB, as a record carries it (`memoryAtTotalPeak`).
public struct MemoryBreakdown: Codable, Sendable {
    public let hostResidentMB: Double
    public let hostAttributedMB: Double
    public let externalMB: Double
    public let graphicsMB: Double?
    public let graphicsCompressedMB: Double?
    public let neuralMB: Double?
    public let neuralCompressedMB: Double?
    public let graphicsNoFootprintMB: Double?
    public let neuralNoFootprintMB: Double?
    public let metalAllocatedMB: Double?
    public let mappedWeightsMB: Double?
    /// Place 3 as measured (`MemoryMonitor.Overlap`): the wrapped pages in RAM; both
    /// overlaps, then each (with `external`, with the footprint); the pages only the GPU
    /// holds (place 3 less the overlaps, what the total adds); the wrapped regions' sizes.
    public let wrappedResidentMB: Double?
    public let overlapMB: Double?
    public let overlapExternalMB: Double?
    public let overlapFootprintMB: Double?
    public let wrappedGPUOnlyMB: Double?
    public let wrappedLocatedMB: Double?
    public let acceleratorPresentMB: Double?
    public let acceleratorAttributedMB: Double?
    public let residentInRAMRecomputedMB: Double?
    public let totalMB: Double?

    public init(_ r: MemoryMonitor.Reading) {
        func mb(_ bytes: UInt64) -> Double { Double(bytes) / MemoryMonitor.mib }
        let accelerator = r.hasLedger || r.metalAllocatedBytes != nil
        hostResidentMB = mb(r.residentBytes)
        hostAttributedMB = mb(r.footprintBytes)
        externalMB = mb(r.externalBytes)
        graphicsMB = r.hasLedger ? mb(r.graphicsBytes) : nil
        graphicsCompressedMB = r.hasLedger ? mb(r.graphicsCompressedBytes) : nil
        neuralMB = r.hasLedger ? mb(r.neuralBytes) : nil
        neuralCompressedMB = r.hasLedger ? mb(r.neuralCompressedBytes) : nil
        graphicsNoFootprintMB = r.hasLedger ? mb(r.graphicsNoFootprintBytes) : nil
        neuralNoFootprintMB = r.hasLedger ? mb(r.neuralNoFootprintBytes) : nil
        metalAllocatedMB = r.metalAllocatedBytes.map(mb)
        mappedWeightsMB = r.metalAllocatedBytes != nil ? mb(r.mappedWeightsBytes) : nil
        wrappedResidentMB = r.overlap.map { mb($0.residentBytes) }
        overlapMB = r.overlapCountedBytes.map(mb)
        overlapExternalMB = r.overlap.map { mb($0.externalBytes) }
        overlapFootprintMB = r.overlap.map { mb($0.footprintBytes) }
        wrappedGPUOnlyMB = r.overlap.map { mb($0.gpuOnlyBytes) }
        wrappedLocatedMB = r.overlap.map { mb($0.locatedBytes) }
        acceleratorPresentMB = accelerator ? mb(r.acceleratorPresentBytes) : nil
        acceleratorAttributedMB = r.hasLedger ? mb(r.acceleratorAttributedBytes) : nil
        residentInRAMRecomputedMB = accelerator ? mb(r.residentInRAMBytes) : nil
        totalMB = r.totalBytes.map(mb)
    }
}

/// Records peak physical footprint across a sliding window.
///
/// Every tick takes one `MemoryMonitor.read()`, so all the series below describe
/// the same instants. `phys_footprint` is what jetsam charges the process and it
/// does **not** count clean file-backed pages, so a runtime that memory-maps its
/// weights (LiteRT-LM maps its model, llama.cpp maps the whole GGUF) reads far
/// lower than one that allocates them (MLX) — the asymmetry that makes a raw
/// footprint column non-comparable across runtimes. `resident_size` counts the
/// mapped pages while they are in the page table, and a GPU that holds a mapped
/// file's pages outside the page table shows in Metal's figure alone; `accounting`
/// carries every place and a total that counts each page once. Prefer medians to
/// resident peaks: mapped pages fault in and out, so peak resident is page-cache
/// noise (66-281% run-to-run, measured 2026-07-26).
///
/// Place 3 and its overlaps are measured at the first tick, again once `external`,
/// `internal` or Metal's figure beyond the ledger has moved by 16 MiB (250 ms apart at
/// least) or while place 3 itself moved 16 MiB at the last measurement (a wrapped file
/// the GPU reads for the first time pages in over seconds), and every 2 s while the
/// process has wrapped regions, since the GPU touching a wrapped page moves none of
/// those counters.
public actor MemorySampler {
    public private(set) var peakMB: Double = 0
    public private(set) var peakResidentMB: Double = 0
    private var footprintSamples: [Double] = []
    private var residentSamples: [Double] = []
    private var externalSamples: [Double] = []
    private var presentSamples: [Double] = []
    private var attributedSamples: [Double] = []
    private var residentInRAMSamples: [Double] = []
    private var totalSamples: [Double] = []
    private var peakExternal: Double = 0
    private var peakPresent: Double = 0
    private var peakAttributed: Double = 0
    private var peakResidentInRAM: Double = 0
    private var peakTotal: Double = -1
    private var totalPeakReading: MemoryMonitor.Reading?
    private var totalMissing = false
    private var ledgerSeen = false
    private var acceleratorSeen = false
    private var overlapCache: MemoryMonitor.Overlap?
    private var overlapAt: (external: UInt64, internal: UInt64, mapped: UInt64, uptimeNS: UInt64)?
    private var overlapUnavailable = false
    private var placeThreeMoving = false
    private var overlapQueries = 0
    private var overlapQueryNS: UInt64 = 0
    private var task: Task<Void, Never>?
    private var trace: MemoryTrace?
    private var traceRegionsAtNS: UInt64 = 0

    public init() {}

    /// Median of the sampled footprints — steadier than the peak when a run has a brief
    /// allocation spike.
    public var medianMB: Double { Self.median(footprintSamples) }

    /// Median of the sampled resident sizes. **Use this, not `peakResidentMB`.** Resident
    /// size counts mapped-and-resident file pages, which the kernel faults in and evicts
    /// under memory pressure, so the instantaneous peak is dominated by page-cache noise:
    /// measured 2026-07-26, peak resident swung 66% (LiteRT-LM) and 281% (MLX) across three
    /// identical runs while the footprint held to ~1%.
    public var medianResidentMB: Double { Self.median(residentSamples) }

    /// Last sample taken — the settled value at the end of the window.
    public var finalResidentMB: Double { residentSamples.last ?? 0 }

    public var sampleCount: Int { footprintSamples.count }

    /// Every place over the window (`MemoryMonitor`), or nil before the first sample.
    public var accounting: MemoryAccounting? {
        #if !os(macOS)
        // The three places and the total are macOS only until they have run on an iPhone:
        // an iOS record keeps the fields it had before them.
        return nil
        #else
        guard !footprintSamples.isEmpty else { return nil }
        let total = !totalMissing && !totalSamples.isEmpty
        return MemoryAccounting(
            peakExternalMB: peakExternal,
            medianExternalMB: Self.median(externalSamples),
            peakAcceleratorPresentMB: acceleratorSeen ? peakPresent : nil,
            medianAcceleratorPresentMB: acceleratorSeen ? Self.median(presentSamples) : nil,
            peakAcceleratorAttributedMB: ledgerSeen ? peakAttributed : nil,
            medianAcceleratorAttributedMB: ledgerSeen ? Self.median(attributedSamples) : nil,
            peakResidentInRAMMB: acceleratorSeen ? peakResidentInRAM : nil,
            medianResidentInRAMMB: acceleratorSeen ? Self.median(residentInRAMSamples) : nil,
            peakTotalMB: total ? peakTotal : nil,
            medianTotalMB: total ? Self.median(totalSamples) : nil,
            atTotalPeak: total ? totalPeakReading.map(MemoryBreakdown.init) : nil,
            overlapQueries: overlapQueries,
            overlapQueryMS: Double(overlapQueryNS) / 1e6)
        #endif
    }

    public func start(intervalMS: Int = 100) {
        stop()
        footprintSamples.removeAll()
        residentSamples.removeAll()
        externalSamples.removeAll()
        presentSamples.removeAll()
        attributedSamples.removeAll()
        residentInRAMSamples.removeAll()
        totalSamples.removeAll()
        peakMB = 0
        peakResidentMB = 0
        peakExternal = 0
        peakPresent = 0
        peakAttributed = 0
        peakResidentInRAM = 0
        peakTotal = -1
        totalPeakReading = nil
        totalMissing = false
        ledgerSeen = false
        acceleratorSeen = false
        overlapCache = nil
        overlapAt = nil
        overlapUnavailable = false
        placeThreeMoving = false
        overlapQueries = 0
        overlapQueryNS = 0
        trace = MemoryTrace.fromEnvironment()
        traceRegionsAtNS = 0
        // The reading at the start seeds the peaks without counting as a sample.
        if let r = MemoryMonitor.read(includeMetal: Self.readsMetal) { note(withOverlap(r), asSample: false) }
        task = Task { [weak self] in
            while !Task.isCancelled {
                if let r = MemoryMonitor.read(includeMetal: Self.readsMetal) { await self?.sample(r) }
                try? await Task.sleep(nanoseconds: UInt64(intervalMS) * 1_000_000)
            }
        }
    }

    public func stop() {
        task?.cancel()
        task = nil
        trace = nil
    }

    private func sample(_ r: MemoryMonitor.Reading) {
        note(withOverlap(r), asSample: true)
    }

    /// macOS reads Metal's figure every tick (place 3); iOS reads `task_info` alone, as the sampler did before
    /// the three places (then two calls: `TASK_VM_INFO` and `MACH_TASK_BASIC_INFO`; now the one `TASK_VM_INFO`).
    #if os(macOS)
    private static let readsMetal = true
    #else
    private static let readsMetal = false
    #endif

    /// The reading with place 3 and the overlaps filled in from the last measurement,
    /// taken again when due (see the type's note).
    private func withOverlap(_ reading: MemoryMonitor.Reading) -> MemoryMonitor.Reading {
        #if !os(macOS)
        // No region query on iOS until it has run on an iPhone (its cost there is unmeasured).
        return reading
        #else
        var r = reading
        let mapped = r.mappedWeightsBytes
        let now = DispatchTime.now().uptimeNanoseconds
        let due: Bool
        if let at = overlapAt {
            let since = now &- at.uptimeNS
            let moved = Self.distance(at.external, r.externalBytes) > Self.overlapMove
                || Self.distance(at.internal, r.internalBytes) > Self.overlapMove
                || Self.distance(at.mapped, mapped) > Self.overlapMove
                || placeThreeMoving
            let wrapped = (overlapCache?.locatedBytes ?? 0) > 0
            due = (moved && since >= 250_000_000) || (wrapped && since >= 2_000_000_000)
        } else {
            due = true
        }
        if due && !overlapUnavailable {
            let measured = MemoryMonitor.measureOverlap(metalBeyondLedger: mapped)
            overlapQueries += 1
            overlapQueryNS &+= DispatchTime.now().uptimeNanoseconds &- now
            if let measured {
                // Still paging in (a wrapped file the GPU reads for the first time): measure
                // again at the movement pace until place 3 holds still.
                placeThreeMoving = Self.distance(overlapCache?.residentBytes ?? 0, measured.residentBytes)
                    > Self.overlapMove
                overlapCache = measured
                overlapAt = (r.externalBytes, r.internalBytes, mapped, now)
            } else {
                overlapUnavailable = true
                overlapCache = nil
            }
        }
        r.overlap = overlapUnavailable ? nil : overlapCache
        return r
        #endif
    }

    private static let overlapMove: UInt64 = 16 * 1024 * 1024

    private static func distance(_ a: UInt64, _ b: UInt64) -> UInt64 { a > b ? a - b : b - a }

    private func note(_ r: MemoryMonitor.Reading, asSample: Bool) {
        let mb = MemoryMonitor.mib
        let footprint = Double(r.footprintBytes) / mb
        let resident = Double(r.residentBytes) / mb
        let external = Double(r.externalBytes) / mb
        let present = Double(r.acceleratorPresentBytes) / mb
        let attributed = Double(r.acceleratorAttributedBytes) / mb
        let residentInRAM = Double(r.residentInRAMBytes) / mb
        if r.hasLedger { ledgerSeen = true }
        if r.hasLedger || r.metalAllocatedBytes != nil { acceleratorSeen = true }
        peakMB = max(peakMB, footprint)
        peakResidentMB = max(peakResidentMB, resident)
        peakExternal = max(peakExternal, external)
        peakPresent = max(peakPresent, present)
        peakAttributed = max(peakAttributed, attributed)
        peakResidentInRAM = max(peakResidentInRAM, residentInRAM)
        if let totalBytes = r.totalBytes {
            let total = Double(totalBytes) / mb
            if total > peakTotal {
                peakTotal = total
                totalPeakReading = r
            }
            if asSample { totalSamples.append(total) }
        } else {
            totalMissing = true
        }
        if let trace {
            trace.write(r)
            let now = DispatchTime.now().uptimeNanoseconds
            if now &- traceRegionsAtNS >= 2_000_000_000 {
                traceRegionsAtNS = now
                trace.regions(overlap: r.overlap, resident: r.residentBytes)
            }
        }
        guard asSample else { return }
        footprintSamples.append(footprint)
        residentSamples.append(resident)
        externalSamples.append(external)
        presentSamples.append(present)
        attributedSamples.append(attributed)
        residentInRAMSamples.append(residentInRAM)
    }

    private static func median(_ xs: [Double]) -> Double {
        guard !xs.isEmpty else { return 0 }
        let s = xs.sorted()
        return s.count % 2 == 1 ? s[s.count / 2] : (s[s.count / 2 - 1] + s[s.count / 2]) / 2
    }
}

/// Opt-in per-sample log of every counter (`BENCH_MEMORY_TRACE=<file>`, appended, one
/// tab-separated line per reading, MiB), for checking a run's memory fields against
/// outside reads (`vmmap`, `footprint`). With it, every 2 s the sampler also logs every
/// region by class (`R` lines, `regions(overlap:resident:)`). Off unless the variable is set.
final class MemoryTrace: @unchecked Sendable {
    private let handle: FileHandle
    private let start = Date()

    static func fromEnvironment() -> MemoryTrace? {
        guard let path = ProcessInfo.processInfo.environment["BENCH_MEMORY_TRACE"], !path.isEmpty
        else { return nil }
        if !FileManager.default.fileExists(atPath: path) {
            FileManager.default.createFile(atPath: path, contents: nil)
        }
        guard let handle = FileHandle(forWritingAtPath: path) else { return nil }
        handle.seekToEndOfFile()
        let trace = MemoryTrace(handle: handle)
        trace.line("# window start \(ISO8601DateFormatter().string(from: Date())) pid \(getpid())\n"
            + "# t_s\tresident\tfootprint\tinternal\texternal\tcompressed\tgraphics\tgraphics_c\t"
            + "neural\tneural_c\tgraphics_nofp\tneural_nofp\tmetal\tmapped_weights\twrapped_resident\t"
            + "overlap\toverlap_ext\toverlap_fp\tgpu_only\tlocated\t"
            + "accel_present\taccel_attributed\tresident_in_ram\ttotal")
        return trace
    }

    private init(handle: FileHandle) { self.handle = handle }

    deinit { try? handle.close() }

    private func mb(_ bytes: UInt64) -> String {
        String(format: "%.1f", Double(bytes) / MemoryMonitor.mib)
    }

    func write(_ r: MemoryMonitor.Reading) {
        let fields = [
            String(format: "%.3f", Date().timeIntervalSince(start)),
            mb(r.residentBytes), mb(r.footprintBytes), mb(r.internalBytes), mb(r.externalBytes),
            mb(r.compressedBytes), mb(r.graphicsBytes), mb(r.graphicsCompressedBytes),
            mb(r.neuralBytes), mb(r.neuralCompressedBytes),
            mb(r.graphicsNoFootprintBytes), mb(r.neuralNoFootprintBytes),
            r.metalAllocatedBytes.map(mb) ?? "", mb(r.mappedWeightsBytes),
            r.overlap.map { mb($0.residentBytes) } ?? "", r.overlapCountedBytes.map(mb) ?? "",
            r.overlap.map { mb($0.externalBytes) } ?? "", r.overlap.map { mb($0.footprintBytes) } ?? "",
            r.overlap.map { mb($0.gpuOnlyBytes) } ?? "", r.overlap.map { mb($0.locatedBytes) } ?? "",
            mb(r.acceleratorPresentBytes), mb(r.acceleratorAttributedBytes),
            mb(r.residentInRAMBytes), r.totalBytes.map(mb) ?? "",
        ]
        line(fields.joined(separator: "\t"))
    }

    /// Every region at one instant, by class (IOAccelerator / IOKit / IOSurface tags; the
    /// short query's wrap candidates (`MemoryMonitor.wrapCandidate(_:)`: shared file,
    /// anonymous, private file); other file mappings; other anonymous memory): pages in the
    /// page table (footprint mode) and compressed, their sum against `resident_size`, and
    /// one line per region of 16 MiB or more with its pages in the page table and in the
    /// VM object (normal mode).
    func regions(overlap: MemoryMonitor.Overlap?, resident: UInt64) {
        typealias Pages = (resident: UInt64, dirty: UInt64, compressed: UInt64)
        let t = String(format: "%.3f", Date().timeIntervalSince(start))
        let all = MemoryMonitor.regions().filter { $0.info.is_submap == 0 }
        var object: [UInt64: Pages] = [:]
        for region in all where Self.isBig(region) {
            object[region.address] = MemoryMonitor.pages(at: region.address)
        }
        let started = DispatchTime.now().uptimeNanoseconds
        _ = MemoryMonitor.setFootprintMode(true)
        var table: [UInt64: Pages] = [:]
        for region in all { table[region.address] = MemoryMonitor.pages(at: region.address) }
        _ = MemoryMonitor.setFootprintMode(false)
        let walkMS = Double(DispatchTime.now().uptimeNanoseconds - started) / 1e6
        var classes: [String: (size: UInt64, table: UInt64, compressed: UInt64, n: Int)] = [:]
        var sum: UInt64 = 0
        for region in all {
            let i = region.info
            let p = table[region.address] ?? (0, 0, 0)
            var c = classes[Self.cls(i)] ?? (0, 0, 0, 0)
            c.size &+= region.size; c.table &+= p.resident; c.compressed &+= p.compressed; c.n += 1
            classes[Self.cls(i)] = c
            sum &+= p.resident
        }
        line("R\t\(t)\tregions \(all.count)\twalk_ms \(String(format: "%.1f", walkMS))"
            + "\twrapped_resident \(overlap.map { mb($0.residentBytes) } ?? "?")"
            + "\toverlap_ext \(overlap.map { mb($0.externalBytes) } ?? "?")"
            + "\toverlap_fp \(overlap.map { mb($0.footprintBytes) } ?? "?")"
            + "\tgpu_only \(overlap.map { mb($0.gpuOnlyBytes) } ?? "?")"
            + "\tlocated \(overlap.map { mb($0.locatedBytes) } ?? "?")"
            + "\tresident \(mb(resident))\ttable_sum \(mb(sum))")
        for (cls, c) in classes.sorted(by: { $0.key < $1.key }) {
            line("R\t\(t)\tclass \(cls)\tn \(c.n)\tsize \(mb(c.size))\ttable \(mb(c.table))\tcompressed \(mb(c.compressed))")
        }
        for region in all where Self.isBig(region) {
            let i = region.info
            let name = i.external_pager != 0 ? Self.fileName(region.address) : "anon"
            line("R\t\(t)\t\(name)\tsize \(mb(region.size))\tclass \(Self.cls(i))\tinh \(i.inheritance)"
                + "\tshare \(i.share_mode)\tref \(i.ref_count)\ttag \(i.user_tag)"
                + "\ttable \(table[region.address].map { mb($0.resident) } ?? "?")"
                + "\tcompressed \(table[region.address].map { mb($0.compressed) } ?? "?")"
                + "\tobject \(object[region.address].map { mb($0.resident) } ?? "?")")
        }
    }

    private static func cls(_ i: vm_region_submap_short_info_data_64_t) -> String {
        switch Int32(i.user_tag) {
        case VM_MEMORY_IOACCELERATOR: return "ioaccelerator"
        case VM_MEMORY_IOKIT: return "iokit"
        case VM_MEMORY_IOSURFACE: return "iosurface"
        default: break
        }
        switch MemoryMonitor.wrapCandidate(i) {
        case .sharedFile: return "wrapped_file"
        case .anonymous: return "wrapped_anon"
        case .privateFile: return "file_private_ref3"
        case nil: return i.external_pager != 0 ? "file" : "anonymous"
        }
    }

    private static func isBig(_ region: MemoryMonitor.Region) -> Bool {
        region.info.is_submap == 0 && region.size >= 16 * 1024 * 1024
    }

    private static func fileName(_ address: UInt64) -> String {
        #if os(macOS)
        var buffer = [CChar](repeating: 0, count: Int(MAXPATHLEN))
        let n = proc_regionfilename(getpid(), address, &buffer, UInt32(buffer.count))
        if n > 0 { return (String(cString: buffer) as NSString).lastPathComponent }
        #endif
        return "?"
    }

    private func line(_ s: String) {
        handle.write(Data((s + "\n").utf8))
    }
}
