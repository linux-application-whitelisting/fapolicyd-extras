#!/usr/bin/env python3

#########
# Usage: # Show a full tree with counts using nice box-drawing glyphs
# fapolicyd-cli --dump | trusttree.py
#
# ASCII-only output
# fapolicyd-cli --dump | trusttree.py --ascii
#
# Focus on /boot/efi only, prune tiny branches (<3 files),
# and collapse linear chains
# fapolicyd-cli --dump | trusttree.py --prefix /boot/efi --min-count 3 --compact
#
# Limit printing to first 3 levels (root=0), last extension only (default)
# fapolicyd-cli --dump | trusttree.py --max-depth 3
#
# Prefer full multi-dot extension buckets (e.g. *.tar.gz) or ignore
# extensions entirely
# fapolicyd-cli --dump | trusttree.py --ext-mode full
# fapolicyd-cli --dump | trusttree.py --ext-mode star
###########

import sys, re, argparse, os, json
from collections import defaultdict

def parse_args():
    p = argparse.ArgumentParser(
        description="Summarize fapolicyd trust DB as a directory tree aggregated by file extension."
    )
    p.add_argument("--ascii", action="store_true",
                   help="Use ASCII tree characters instead of Unicode box drawing.")
    p.add_argument("--min-count", type=int, default=1,
                   help="Prune branches whose total count is below this number. Default: 1 (no prune).")
    p.add_argument("--max-depth", type=int, default=0,
                   help="Limit printed depth (0 = unlimited). Root is depth 0.")
    p.add_argument("--top", type=int, default=0,
                   help="At each level, only show the top N children by count (0 = all).")
    p.add_argument("--prefix", type=str, default="/",
                   help="Only include paths under this prefix (directory). Default: '/'.")
    p.add_argument("--exclude-regex", type=str, default="",
                   help="Exclude paths whose full path matches this regex.")
    p.add_argument("--include-regex", type=str, default="",
                   help="If set, only include paths whose full path matches this regex.")
    p.add_argument("--ext-mode", choices=["last", "full", "star"],
                   default="last",
                   help="How to compute the aggregated extension leaf: "
                        "'last' = last suffix (e.g. .tar.gz -> *.gz), "
                        "'full' = full suffix after first dot (e.g. *.tar.gz), "
                        "'star' = ignore extension altogether (always '*'). Default: last.")
    p.add_argument("--no-counts", action="store_true",
                   help="Do not show counts at each node.")
    p.add_argument("--compact", action="store_true",
                   help="Collapse linear chains with a single child into 'a/b/c' segments.")
    p.add_argument("--json", action="store_true",
                   help="Emit JSON summary instead of a tree.")
    p.add_argument("--emit-filter", action="store_true",
                   help="Emit suggested fapolicyd-filter.conf patterns for the printed/pruned tree.")
    p.add_argument("--emit-filter-mode", choices=["ext", "dir", "all"], default="ext",
                   help="Filter suggestion style: 'ext' = directory + *.ext leaves; "
                        "'dir' = directory globs using **; 'all' = both. Default: ext.")
    return p.parse_args()

class Node:
    __slots__ = ("children", "count")
    def __init__(self):
        self.children = dict()
        self.count = 0

def ensure_path(root, parts):
    cur = root
    cur.count += 1
    for part in parts:
        if part not in cur.children:
            cur.children[part] = Node()
        cur = cur.children[part]
        cur.count += 1

def get_ext_leaf(basename, mode):
    if mode == "star":
        return "*"
    if basename.startswith("."):
        return "*"
    if "." not in basename:
        return "*"
    if mode == "last":
        ext = basename.split(".")[-1]
        return f"*.{ext}" if ext else "*"
    else:
        first_dot = basename.find(".")
        ext = basename[first_dot+1:]
        return f"*.{ext}" if ext else "*"

def path_to_parts(path, mode):
    norm = os.path.normpath(path)
    if norm == "/":
        return ["/", "*"]
    if norm.startswith("/"):
        norm = norm[1:]
        parts = ["/"] + ([p for p in norm.split("/") if p])
    else:
        parts = [p for p in norm.split("/") if p]
        if parts and parts[0] != "/":
            parts = ["/"] + parts

    if parts:
        base = parts[-1]
        ext_leaf = get_ext_leaf(base, mode)
        parts = parts[:-1] + [ext_leaf]
    else:
        parts = ["/", "*"]
    return parts

def compile_filters(args):
    include_re = re.compile(args.include_regex) if args.include_regex else None
    exclude_re = re.compile(args.exclude_regex) if args.exclude_regex else None
    return include_re, exclude_re

def want_path(path, prefix, include_re, exclude_re):
    if prefix and not path.startswith(prefix):
        return False
    if include_re and not include_re.search(path):
        return False
    if exclude_re and exclude_re.search(path):
        return False
    return True

def read_paths_from_stdin():
    for raw in sys.stdin:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            yield parts[1]
        else:
            m = re.match(r"^\S+\s+(\S+)", line)
            if m:
                yield m.group(1)

def build_tree(args):
    include_re, exclude_re = compile_filters(args)
    root = Node()
    for path in read_paths_from_stdin():
        if not want_path(path, args.prefix, include_re, exclude_re):
            continue
        parts = path_to_parts(path, args.ext_mode)
        ensure_path(root, parts)
    return root

def prune_tree(node, min_count):
    if node.count < min_count:
        return None
    new_children = {}
    for name, child in node.children.items():
        kept = prune_tree(child, min_count)
        if kept is not None:
            new_children[name] = kept
    node.children = new_children
    return node

def collapse_chains(name, node):
    cur_name = name
    cur_node = node
    while len(cur_node.children) == 1:
        (child_name, child_node), = cur_node.children.items()
        cur_name = f"{cur_name}/{child_name}" if cur_name else child_name
        cur_node = child_node
    collapsed_children = {}
    for ch_name, ch_node in cur_node.children.items():
        nname, nnode = collapse_chains(ch_name, ch_node)
        collapsed_children[nname] = nnode
    cur_node.children = collapsed_children
    return cur_name, cur_node

def is_leaf_name(name):
    return name == "*" or name.startswith("*.")

def sorted_children(node):
    return sorted(node.children.items(), key=lambda kv: (is_leaf_name(kv[0]), -kv[1].count, kv[0]))

def to_json(name, node):
    return {
        "name": name,
        "count": node.count,
        "children": [to_json(k, v) for k, v in sorted_children(node)]
    }

def print_tree(root_node, use_ascii=False, show_counts=True, max_depth=0, top=0, compact=False):
    working = Node()
    working.children = dict(root_node.children)
    working.count = root_node.count

    if compact:
        collapsed_children = {}
        for name, child in working.children.items():
            nname, nnode = collapse_chains(name, child)
            collapsed_children[nname] = nnode
        working.children = collapsed_children

    if use_ascii:
        tee, corner, pipe, dash = "|-- ", "`-- ", "|   ", "    "
    else:
        tee, corner, pipe, dash = "├── ", "└── ", "│   ", "    "

    root_label = "/"
    print(f"{root_label} [{working.count}]" if show_counts else root_label)

    def _print(node, prefix, depth):
        items = sorted_children(node)
        if top and len(items) > top:
            items = items[:top]
        for i, (name, child) in enumerate(items):
            is_last = (i == len(items) - 1)
            connector = corner if is_last else tee
            line = prefix + connector + name
            if show_counts:
                line += f" [{child.count}]"
            print(line)
            if max_depth and depth + 1 >= max_depth:
                continue
            new_prefix = prefix + (dash if is_last else pipe)
            _print(child, new_prefix, depth + 1)

    _print(working, "", 0)

def collect_filters(node, path_stack, mode):
    """
    Produce suggested filter patterns from the *current* pruned tree.
    - For ext mode: emit directory path + *.ext leaves
    - For dir mode: emit directory/** for internal nodes
    Returns a set of strings.
    """
    out = set()
    def is_leaf(nm):
        return nm == "*" or nm.startswith("*.")
    def current_dir_path(stack):
        if not stack:
            return "/"
        elems = []
        for s in stack:
            if s == "/":
                continue
            if s == "*" or s.startswith("*."):
                continue
            elems.append(s)
        return "/" + "/".join(elems) if elems else "/"

    def walk(name, node, stack):
        stack.append(name)
        if is_leaf(name):
            d = current_dir_path(stack[:-1])
            if mode in ("ext","all"):
                out.add(os.path.join(d, name))
        else:
            if mode in ("dir","all"):
                d = current_dir_path(stack)
                out.add(os.path.join(d, "**"))
            for ch_name, ch_node in node.children.items():
                walk(ch_name, ch_node, stack)
        stack.pop()

    for name, child in node.children.items():
        walk(name, child, [])
    return out

def main():
    args = parse_args()
    tree = build_tree(args)
    tree = prune_tree(tree, args.min_count)
    if tree is None or not tree.children:
        return

    if args.json:
        def json_slice(name, node, depth):
            obj = {"name": name, "count": node.count, "children": []}
            if args.max_depth and depth >= args.max_depth:
                return obj
            items = sorted_children(node)
            if args.top and len(items) > args.top:
                items = items[:args.top]
            for ch_name, ch_node in items:
                obj["children"].append(json_slice(ch_name, ch_node, depth+1))
            return obj

        root_obj = {"name": "/", "count": tree.count, "children": []}
        items = sorted_children(tree)
        if args.top and len(items) > args.top:
            items = items[:args.top]
        for ch_name, ch_node in items:
            root_obj["children"].append(json_slice(ch_name, ch_node, 1))
        print(json.dumps(root_obj, indent=2))
        if args.emit_filter:
            filters = collect_filters(tree, [], args.emit_filter_mode)
            for f in sorted(filters):
                print(f"#FILTER {f}")
        return

    print_tree(tree, use_ascii=args.ascii, show_counts=not args.no_counts,
               max_depth=args.max_depth, top=args.top, compact=args.compact)

    if args.emit_filter:
        filters = collect_filters(tree, [], args.emit_filter_mode)
        for f in sorted(filters):
            print(f, file=sys.stderr)

if __name__ == "__main__":
    main()
