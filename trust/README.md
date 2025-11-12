## Quickstart
This utility allows you to explore the trust database and see what all is contained it in. It reads fapolicyd-cli --dump from stdin, extracts the path (2nd field), groups files by directory and extension wildcard (e.g., *.py, *.html, or * if no extension), and prints a pstree-style outline with counts. You can tweak depth, pruning, ASCII vs Unicode, etc.

Here are some example uses:

```
# Clean root line, Unicode tree, counts
fapolicyd-cli --dump | python3 trusttree.py

# ASCII-only
fapolicyd-cli --dump | python3 trusttree.py --ascii

# Focus under /boot/efi, keep only top 5 branches per level, and collapse linear chains
fapolicyd-cli --dump | python3 trusttree.py --prefix /boot/efi --top 5 --compact

# Limit to depth 3, prune tiny branches (<5 files)
fapolicyd-cli --dump | python3 trusttree.py --max-depth 3 --min-count 5

# JSON for scripting
fapolicyd-cli --dump | python3 trusttree.py --json > trust.json

# Emit suggested filter patterns (to stderr) for extension leaves
fapolicyd-cli --dump | python3 trusttree.py --emit-filter 2> filters.txt

# Emit *directory* globs (**), not per-extension leaves
fapolicyd-cli --dump | python3 trusttree.py --emit-filter --emit-filter-mode dir 2> dir_filters.txt

# Combine: top-heavy snapshot for /usr, JSON + filter suggestions
fapolicyd-cli --dump \
  | python3 trusttree.py --prefix /usr --top 8 --max-depth 4 --json --emit-filter > usr.json
```

## What it prints (example)
```
/ [9]
└── //boot/efi [9]
    ├── EFI [7]
    │   ├── fedora [5]
    │   │   ├── *.efi [4]
    │   │   └── *.CSV [1]
    │   └── BOOT [2]
    │       ├── *.EFI [1]
    │       └── *.efi [1]
    ├── System/Library/CoreServices/*.plist [1]
    └── * [1]

```

Leaves are aggregated by *.ext (or * if no suffix). Counts are the number of files contributing under that node—handy for spotting “fat” directories to exclude in fapolicyd-filter.conf.

## Useful flags (all optional)
```
  -h, --help            show this help message and exit
  --ascii               Use ASCII tree characters instead of Unicode box
                        drawing.
  --min-count MIN_COUNT
                        Prune branches whose total count is below this number.
                        Default: 1 (no prune).
  --max-depth MAX_DEPTH
                        Limit printed depth (0 = unlimited). Root is depth 0.
  --top TOP             At each level, only show the top N children by count
                        (0 = all).
  --prefix PREFIX       Only include paths under this prefix (directory).
                        Default: '/'.
  --exclude-regex EXCLUDE_REGEX
                        Exclude paths whose full path matches this regex.
  --include-regex INCLUDE_REGEX
                        If set, only include paths whose full path matches
                        this regex.
  --ext-mode {last,full,star}
                        How to compute the aggregated extension leaf: 'last' =
                        last suffix (e.g. .tar.gz -> *.gz), 'full' = full
                        suffix after first dot (e.g. *.tar.gz), 'star' =
                        ignore extension altogether (always '*'). Default:
                        last.
  --no-counts           Do not show counts at each node.
  --compact             Collapse linear chains with a single child into
                        'a/b/c' segments.
  --json                Emit JSON summary instead of a tree.
  --emit-filter         Emit suggested fapolicyd-filter.conf patterns for the
                        printed/pruned tree.
  --emit-filter-mode {ext,dir,all}
                        Filter suggestion style: 'ext' = directory + *.ext
                        leaves; 'dir' = directory globs using **; 'all' =
                        both. Default: ext.

```
Note: this utility is "as is" and not supported.
