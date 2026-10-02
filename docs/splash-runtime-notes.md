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

## Two rules that fail silently

### Reading an undeclared field throws

A record that does not declare a field is not `nil` when you read it. It
traps:

```text
[E] splash:326:10 - property needs_key not found in prototype chain
```

Every record written in a literal must declare the same field set, with empty
defaults, rather than relying on an optional field being absent.

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
