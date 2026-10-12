use makepad_script::{ScriptCode, ScriptHeap, ScriptThreads};

fn main() {
    let mut heap = ScriptHeap::empty();
    let maximum = 2 * 1024 * 1024;
    heap.set_max_heap_bytes(Some(maximum));
    for index in 0..4 {
        let text = format!("{index}{}", "x".repeat(425_000));
        let value = heap.new_string_from_str(&text);
        assert!(!value.is_nil());
    }
    // Four strings are below the original 128-string growth threshold.
    assert!(heap.needs_gc(), "byte pressure must trigger collection");
    heap.mark(&ScriptThreads::empty(), &ScriptCode::default());
    heap.sweep(false);
    assert!(heap.accounted_heap_bytes() < maximum * 3 / 4);
    assert_eq!(heap.max_heap_bytes(), Some(maximum));
    heap.new_string_from_str(&"y".repeat(maximum + 1));
    assert!(heap.take_heap_limit_exceeded(), "hard byte cap remains enforced");
    println!("PASS: byte pressure triggers GC with four strings; hard heap cap unchanged and enforced");
}
