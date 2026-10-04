# Splash runtime notes

Verified against the pinned host (`makepad` 6cf0385) by reading
`platform/script/src/string.rs` and `array.rs` and by running bundles under
`card-host`. These are properties of the runtime, not of any one module. Most
of them fail loudly, but several fail in ways that look like "the feed is just
empty", which costs hours.

## The real method surface

Verified string methods:

```text
len  trim  replace  split  index  search  match_str  captures
match_all  parse_json  to_chars  to_f64  strip_prefix  strip_suffix
url_encode  url_decode
```

Verified array methods:

```text
len  push  pop  remove  retain  clear  to_string  parse_json
```

Globals in use: `regex` `time_now` `floor` `fs` `start_timeout`
`start_interval` `stop_timer`.

**Not available:** `lower` `upper` `contains` `sort` `range` `get` `has` `map`
`filter` `join` as methods. `lower`/`upper`/`len`/`slice`/`split` exist only as
`text.*` standard-library functions, not as string methods.

Consequences worth remembering:

- case-insensitive matching goes through `regex(pattern, "i").test(s)`, not a
  `contains` helper;
- ranking needs an explicit loop, because there is no array sort;
- numeric ranges need a counter loop (`for i in 30`) rather than `range()`.

Indexing `array[i]` works, including on arrays returned by `parse_json()`.

Iterating a **map yields its values, not its keys**. `for entry in some_map`
binds the stored record; `some_map[entry]` is then an unknown key and reads
back as `nil`. To test keys, iterate the key list separately.

A `let` with a name that another file also declares **silently shadows** the
earlier one rather than erroring. Two modules declaring `weather_days` — one as
a list of day-of-month strings, one as a forecast horizon — produced a cascade
of "variable not found" errors far from the cause. Keep top-level names unique
across the assembled bundle; `assemble.py` emits its own, so check both sides.

A map key first written after the literal starts empty, and `push` onto a
global array from inside a function, do not reliably read back. Prefer carrying
the value through a return value.

`&&` / `||` cannot be assumed to short-circuit. Do not rely on `a != nil &&
a["field"]` to protect a dereference; check in separate statements.

## Rules that fail silently

### Reading an undeclared field throws

A record that does not declare a field is not `nil` when you read it. It
traps:

```text
[E] splash:326:10 - property needs_key not found in prototype chain
```

Every record written in a literal must declare the same field set, with empty
defaults, rather than relying on an optional field being absent. This also
applies to a field you intend to assign later: `fx_ingest` writes
`table.fetched_at`, so the table literal in `fx_table_from_upstream` has to
declare it.

### An undeclared map key is nil, and nil has no len()

`rows_by["new_source"]` for a key that was never declared reads as `nil`, and
`nil.len()` traps:

```text
[E] splash:469:29 - method len not found on nil
```

So a new source id must be added to every map that is keyed by source id, not
just to the list of sources. Prefer initializing such maps in one function
driven by the source list, as `feed_initialize()` does, so the two cannot
drift apart.

### Map keys must be ASCII identifiers

`{w北京: []}` does not parse. Use `w01`, `w02`, … and resolve names through a
lookup, as `cities.json` does with `cid`.

### `<` and `>` on text are always false

Only `==` and `!=` compare strings. Every ordering comparison against a text
value returns `false`, silently:

```text
"b" > "a"                  -> false
"2026-10-01" > "2026-09-30" -> false
```

ISO dates happen to sort correctly as text, which makes this the most expensive
kind of bug: the code reads correctly and never fires. `fx_ingest` orders its
loaded days by `weather_time_stamp(day)` instead, and numbers compare fine.
Grep for `>` or `<` against anything that is not known to be a number before
trusting it.

### A JSON object is opaque

A value from `parse_json()` cannot be inspected as a collection:

- `obj.len()` reports `0` for any number of members. The real daily rate file
  has 340 entries and still reports 0, so a size check built on `len()` accepts
  an empty document and rejects a full one.
- Iterating it yields values, not keys, and there is no `keys()`, `entries()`
  or `values()` method — only `len` is registered for objects.

So an upstream payload can only be validated on the keys you can name. `fx_table_valid`
checks the date and the base, and `fx_amount` re-checks the ISO code and the
positive amount on every read. Do not write a "is this table complete" check
against an untrusted JSON object; it cannot be written.

### Module state does propagate

Verified directly, because an earlier note in `holidays.splash` claimed
otherwise and was wrong: writing a map key, pushing onto a top level array, and
assigning a top level scalar from inside a function are all visible afterwards,
including after the global has been reassigned. `fx_reset` relies on this.

The one real trap next to it is iteration order and content: iterating a map
gives its values, so a set cannot be recovered by iterating a map keyed by
id. Keep a plain array for anything that has to be walked.

## Widgets

A widget declared `visible: false` does not reliably reappear when
`set_visible(true)` is called later; the declaration is re-applied on the next
`render()`. Render conditional UI inside an `on_render` that already runs
instead of toggling a hidden declaration. `ui.list` re-renders, so a filter row
placed as the first child of the list always works.

`on_render` callbacks only run when their widget's `.render()` is called
explicitly. `render_main()` calls `ui.tabbar.render()` for exactly this reason;
a new `on_render` needs the same treatment.

## Tooling

- `octoscript check <file>` — syntax only. It is **stricter than the runtime**
  and reports false positives for Makepad extensions (`#x` colors, `+:`,
  two-variable `for`), and it rejects `.len()` on strings, which the runtime
  accepts. `main` reports 32 such diagnostics on a clean tree. Treat its output
  as "no syntax errors", not "valid".
- `octoscript eval` — runs the canonical profile, which lacks the Makepad
  methods. It is not a valid oracle for splash behavior. Do not conclude a
  method is unavailable from an `eval` failure.
- `card-host --bundle bundle --allow-unsigned` — runs the real splash runtime
  and prints `[E] splash:…` with line and column. This is the oracle.
  `hub stamp <dir>` first, since a digest mismatch is refused before the script
  runs.

To observe state from a probe, append a `start_timeout` that writes a JSON
file with `fs.write` and read it from the app-data directory; there is no
`print`. Make the probe report a value rather than just "no error".

## Conditional widget bindings

The current card-host produced `pop_stack_value on empty stack` when a named `TextInput` binding lived in a conditional on_render branch that was skipped. The full intent panel passed after making that optional input anonymous, with edits handled by on_change. Keep identifiers on stable controls, or use a stable outer view for optional UI; do not depend on a conditional binding that has not been emitted.
