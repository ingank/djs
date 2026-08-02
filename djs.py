#!/usr/bin/env python3
"""
djs.py
"""


import argparse
import datetime
import hashlib
import subprocess
import sys
import os
from pathlib import Path
from collections import Counter, defaultdict
from typing import TextIO


APP_NAME = "djs.py"
APP_VERSION = "v0.02"
AUDIO_FLAC = ("flac",)
AUDIO_LOSSLESS = ("wav", "aiff", "aifc")
AUDIO_LOSSY = ("mp3",)
AUDIO_EXTENSIONS = AUDIO_FLAC + AUDIO_LOSSY + AUDIO_LOSSLESS
START_TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
START_DIR = Path.cwd().resolve()
START_ARGS = " ".join(sys.argv[1:])


# ===========================================================================
# core
# ===========================================================================


def stage_directory_name(command: str) -> Path:
    """
    Return the path of the staging directory for *command*.

    The directory name is derived from the current working directory,
    the command name, and the startup timestamp.
    """
    return Path(START_DIR / f"{command}__{START_TIMESTAMP}")


def report_file_name(command: str) -> Path:
    """
    Return the path of the report file for *command*.

    The file name is derived from the current working directory,
    the command name, and the startup timestamp, using a '.txt'
    extension.
    """
    return Path(START_DIR / f"{command}__{START_TIMESTAMP}.txt")


def latest_report_file(command: str) -> Path | None:
    """
    Return the latest report file for *command* in START_DIR.

    Returns None if no matching report exists.
    """
    files = START_DIR.glob(f"{command}__*.txt")
    latest = max(files, default=None, key=lambda p: p.name)

    return latest


def emit_text(text: str, output: TextIO) -> None:
    """
    Emit a line of text to the console and an optional output stream.

    The text is printed to stdout. If *output* is provided, the same
    line is written to the stream, followed by a newline, and the
    stream is flushed immediately.
    """
    print(text)
    if output:
        output.write(f"{text}\n")
        output.flush()


def emit_comment(text1: str, text2: str, output: TextIO) -> None:
    """
    Emit a comment line.
    """
    emit_text(f"# {text1:<15}{text2}", output)


def emit_header(output: TextIO) -> None:
    """
    Write a standard report header.
    """
    emit_comment("Directory:", f"{START_DIR}", output)
    emit_comment("Command:", f"{APP_NAME} {START_ARGS}", output)
    emit_comment("Timestamp:", f"{START_TIMESTAMP}", output)
    emit_comment("Extensions:", f"{", ".join(AUDIO_EXTENSIONS)}", output)


def emit_reading(path: Path, output: TextIO) -> None:
    emit_comment("Reading:", f"{path}", output)


def emit_scanning(output: TextIO) -> None:
    emit_comment("Scanning:", "Filesystem", output)


def emit_processing(count: int, output: TextIO) -> None:
    emit_comment("Processing:", f"{count} files", output)


def emit_resuming(count: int, output: TextIO) -> None:
    emit_comment("Resuming:", f"{count} files", output)


def emit_skipping(count: int, output: TextIO) -> None:
    emit_comment("Skipping:", f"{count} directories", output)


def emit_copied(count: int, output: TextIO) -> None:
    emit_comment("Copied:", f"{count} lines", output)


def emit_listed(count: int, output: TextIO) -> None:
    emit_comment("Listed:", f"{count} files", output)


def emit_hashed(count: int, output: TextIO) -> None:
    emit_comment("Hashed:", f"{count} files", output)


def emit_footer(output: TextIO) -> None:
    """
    Write a standard report footer.
    """
    emit_comment("Status:", "OK", output)


def parse_filelist(filelist: Path) -> list[Path]:
    """
    Parse a text file containing relative file paths.

    Blank lines and lines beginning with '#' are ignored. All remaining
    lines are interpreted as relative file paths and returned as Path
    objects in the order they appear.
    """
    files: list[Path] = []

    with filelist.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            files.append(Path(line))

    return files


def parse_hashlist(hashlist: Path) -> list[tuple[str, Path]]:
    """
    Parse a text file containing SHA-256 hash records.

    Blank lines and lines beginning with '#' are ignored. All remaining
    lines are split into a SHA-256 hash and a relative file path.

    Returns a list of (hash, Path) tuples in the order they appear.
    """
    records: list[tuple[str, Path]] = []

    with hashlist.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            digest, filename = line.split(maxsplit=1)
            records.append((digest, Path(filename)))

    return records


def hash_record(file: Path) -> str:
    """
    Return the hash record for *file*.

    Computes the SHA-256 hash of the normalized audio stream and returns
    a single text line in the format:

        <SHA256> <RELATIVE_PATH>
    """
    return f"{sha256(START_DIR / file)} {file}"


def find_files(start_dir: Path, extensions: list[str]) -> tuple[list[Path], list[Path]]:
    """
    Recursively discover files below *start_dir*.

    Directories whose name begins with '.' are excluded from the traversal,
    including all of their subdirectories.

    Performs a depth-first traversal using os.scandir() for efficiency.
    File extensions are matched case-insensitively, and symbolic links
    are not followed.
    """
    allowed_exts = {"." + ext.lower().lstrip(".") for ext in extensions}
    found_files: list[Path] = []
    skipped_dirs: list[Path] = []
    dirs_to_visit: list[Path] = [start_dir]

    while dirs_to_visit:
        current_dir = dirs_to_visit.pop()

        if current_dir != start_dir and current_dir.name.startswith("."):
            skipped_dirs.append(current_dir.relative_to(start_dir))
            continue

        with os.scandir(current_dir) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    dirs_to_visit.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    path = Path(entry.path)
                    if path.suffix.lower() in allowed_exts:
                        found_files.append(path.relative_to(start_dir))

    found_files.sort()
    skipped_dirs.sort()
    return (found_files, skipped_dirs)


def sha256(file: Path) -> str:
    """
    Compute a deterministic SHA-256 hash of the decoded audio stream by
    hashing normalized PCM data produced by ffmpeg.

    Raises:
        RuntimeError: If ffmpeg fails to decode or process the audio.
    """
    file = Path(file)
    cmd = [
        "ffmpeg", "-v", "error",
        "-i", str(file),
        "-map", "0:a:0",
        "-vn",
        "-f", "s24le",
        "-acodec", "pcm_s24le",
        "-ar", "96000",
        "-ac", "2",
        "-"
    ]
    hasher = hashlib.sha256()
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    assert proc.stdout is not None
    try:
        for chunk in iter(lambda: proc.stdout.read(1024 * 1024), b""):
            hasher.update(chunk)
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass
        ret = proc.wait()
        err_out = b""
        if proc.stderr is not None:
            try:
                err_out = proc.stderr.read()
            finally:
                proc.stderr.close()
        if ret != 0:
            raise RuntimeError(
                f"ffmpeg hashing failed with code {ret} for {file}\n"
                f"{err_out.decode('utf-8', errors='ignore')}"
            )
    return hasher.hexdigest()


# ===========================================================================
# commands
# ===========================================================================


def cmd_copy(args):
    print(f"Dummy: copy ({args.hashfile})")


def cmd_diff(args):
    print(f"Dummy: diff ({args.hashfile1}, {args.hashfile2})")


def cmd_dupes(args):
    print("Dummy: dupes")


def cmd_encode(args):
    print("Dummy: encode")


def cmd_finalize(args):
    print("Dummy: finalize")


def cmd_find(args):
    """
    Find supported audio files and generate a report.

    Searches the configured start directory recursively for files with
    supported audio extensions. The report contains summary statistics
    (found, skipped, processed) followed by the list of all discovered
    files.
    """
    report_file = report_file_name("find").open("w", encoding="utf-8")
    emit_header(report_file)
    emit_scanning(report_file)
    files, skipped = find_files(START_DIR, AUDIO_EXTENSIONS)
    emit_skipping(len(skipped), report_file)
    emit_processing(len(files), report_file)

    processed = 0
    for file in files:
        emit_text(f"{file}", report_file)
        processed += 1

    emit_listed(processed, report_file)
    emit_footer(report_file)
    report_file.close()


def cmd_hashread(args):
    print("Dummy: hashread")


def cmd_hashscan(args):
    """
    Generate SHA-256 hashes for the selected audio files.

    The input file list is taken from one of the following sources:

    - an explicitly specified file list,
    - the most recent 'find' report,
    - or a fresh filesystem scan.

    When resume mode is enabled, the most recent hashscan report is read,
    its existing hash records are copied into the new report, and only the
    remaining files are hashed.
    """
    skipped = 0
    latest_find = latest_report_file("find")
    latest_hashscan = latest_report_file("hashscan")
    rep_file = report_file_name("hashscan").open("w", encoding="utf-8")
    emit_header(rep_file)

    if args.filelist:
        filelist = Path(args.filelist)
        emit_reading(filelist, rep_file)
        files = parse_filelist(filelist)

    elif args.lastfilelist:
        if latest_find is None:
            raise RuntimeError("No previous find report found.")

        short = latest_find.relative_to(START_DIR)
        emit_reading(short, rep_file)
        files = parse_filelist(latest_find)

    else:
        emit_scanning(rep_file)
        files, skipped = find_files(START_DIR, AUDIO_EXTENSIONS)

    previous_records: list[tuple[str, Path]] = []

    if args.resume:
        if latest_hashscan is None:
            raise RuntimeError("No previous hashscan report found.")

        short = latest_hashscan.relative_to(START_DIR)
        emit_reading(short, rep_file)
        previous_records = parse_hashlist(latest_hashscan)
        completed = {path for _, path in previous_records}
        emit_resuming(len(completed), rep_file)
        files = [path for path in files if path not in completed]

    if skipped:
        emit_skipping(len(skipped), rep_file)

    emit_processing(len(files), rep_file)

    copied = 0
    hashed = 0

    for digest, path in previous_records:
        emit_text(f"{digest} {path}", rep_file)
        copied += 1

    for path in files:
        emit_text(hash_record(path), rep_file)
        hashed += 1

    if copied:
        emit_copied(copied, rep_file)

    emit_hashed(hashed, rep_file)
    emit_footer(rep_file)
    rep_file.close()


def cmd_hashwrite(args):
    print("Dummy: hashwrite")


def cmd_match(args):
    print("Dummy: match")


def cmd_merge(args):
    print("Dummy: merge")


def cmd_move(args):
    print("Dummy: move")


def cmd_remux(args):
    print("Dummy: remux")


def cmd_sort(args):
    print("Dummy: sort")


def cmd_stats(args):
    """
    Print statistics about all supported audio files below *START_DIR*.

    Displays the total file count, counts by extension, and a per-directory
    distribution of audio formats.
    """
    rep_file = report_file_name("stats").open("w", encoding="utf-8")
    emit_header(rep_file)
    latest_find = latest_report_file("find")
    latest_hashscan = latest_report_file("hashscan")
    skipped = []

    if args.filelist:
        filelist = Path(args.filelist)
        emit_reading(filelist, rep_file)
        files = parse_filelist(filelist)

    elif args.hashlist:
        hashlist = Path(args.hashliist)
        emit_reading(hashlist, rep_file)

    elif args.lastfilelist:
        if latest_find is None:
            raise RuntimeError("No previous find report found.")

        short = latest_find.relative_to(START_DIR)
        emit_reading(short, rep_file)
        files = parse_filelist(latest_find)

    elif args.lasthashlist:
        if latest_hashscan is None:
            raise RuntimeError("No previous hashscan report found.")

        short = latest_hashscan.relative_to(START_DIR)
        emit_reading(short, rep_file)
        data = parse_hashlist(latest_hashscan)
        files = {path for _, path in data}

    else:
        emit_scanning(rep_file)
        files, skipped = find_files(START_DIR, AUDIO_EXTENSIONS)

    # collect stats
    ext_counter = Counter()
    dir_counter = defaultdict(Counter)

    for path in files:
        ext_counter[path.suffix.lower()] += 1
        dir_counter[path.parent][path.suffix.lower()] += 1

    stats = {
        "file_count": len(files),
        "extensions": dict(ext_counter),
        "directories": {
            directory: dict(counter)
            for directory, counter in dir_counter.items()
        },
    }

    # emit stats
    dir_count = len(stats['directories'])
    emit_text(f"Processed audio files: {stats['file_count']}", rep_file)

    for ext, count in sorted(stats["extensions"].items()):
        emit_text(f"   {ext} ({count})", rep_file)

    emit_text(f"Directories containing audio files: {dir_count}", rep_file)

    for directory in sorted(stats["directories"]):
        line = ", ".join(
            f"{ext} ({count})"
            for ext, count in sorted(stats["directories"][directory].items())
        )
        emit_text(f"   .\\{directory}: {line}", rep_file)

    if skipped:
        emit_text(f"Skipped directories: {len(skipped)}", rep_file)
        for directory in sorted(skipped):
            emit_text(f"   .\\{directory}", rep_file)

    emit_footer(rep_file)
    rep_file.close()


def cmd_tagexport(args):
    print("Dummy: tagexport")


def cmd_helpall(args):
    """
    Display the main help followed by the help text
    of every available subcommand.
    """
    parser = args.parser
    parser.print_help()

    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, subparser in action.choices.items():
                print()
                print("-" * (len(name) + 9))
                print("command:", name)
                print("-" * (len(name) + 9))
                subparser.print_help()


# ===========================================================================
# cli parser
# ===========================================================================


def build_parser():
    parser = argparse.ArgumentParser(
        prog="djs.py",
        description=f"DJS // DJ-Suite (audio and hash utilities) // {APP_VERSION}",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        metavar="<command>",
    )

    # -----------------------------------------------------------------------
    # copy
    # -----------------------------------------------------------------------

    p = subparsers.add_parser(
        "copy",
        help="Copy files based on a hash file.",
        description="Copy files based on a hash file.",
    )
    p.add_argument("hashfile", help="hash file")
    p.set_defaults(func=cmd_copy)

    # -----------------------------------------------------------------------
    # diff
    # -----------------------------------------------------------------------

    p = subparsers.add_parser(
        "diff",
        help="Compare two hash files.",
        description="Compare two hash files.",
    )
    p.add_argument("hashfile1", help="first hash file")
    p.add_argument("hashfile2", help="second hash file")
    p.set_defaults(func=cmd_diff)

    # -----------------------------------------------------------------------
    # dupes
    # -----------------------------------------------------------------------

    p = subparsers.add_parser(
        "dupes",
        help="Find duplicate hashes in a hash file.",
        description="Find duplicate hashes in a hash file.",
    )
    p.add_argument("hashfile", help="hash file")
    p.set_defaults(func=cmd_dupes)

    # -----------------------------------------------------------------------
    # encode
    # -----------------------------------------------------------------------

    p = subparsers.add_parser(
        "encode",
        help="Encode original audio files for the workflow.",
        description="Encode original audio files for the workflow.",
    )
    p.set_defaults(func=cmd_encode)

    # -----------------------------------------------------------------------
    # finalize
    # -----------------------------------------------------------------------

    p = subparsers.add_parser(
        "finalize",
        help="Prepare audio files for the playback system.",
        description="Prepare audio files for the playback system.",
    )
    p.add_argument("hashfile", help="hash file")
    p.set_defaults(func=cmd_finalize)

    # -----------------------------------------------------------------------
    # find
    # -----------------------------------------------------------------------

    p = subparsers.add_parser(
        "find",
        help="Find and list audio files.",
        description="Find and list audio files.",
    )
    p.set_defaults(func=cmd_find)

    # -----------------------------------------------------------------------
    # hashread
    # -----------------------------------------------------------------------

    p = subparsers.add_parser(
        "hashread",
        help="Read hash values from audio file tags.",
        description="Read hash values from audio file tags.",
    )
    p.set_defaults(func=cmd_hashread)

    # -----------------------------------------------------------------------
    # hashscan
    # -----------------------------------------------------------------------

    p = subparsers.add_parser(
        "hashscan",
        help="Generate hashes from audio files.",
        description="Generate hashes from audio files.",
    )
    filelist_group = p.add_mutually_exclusive_group()
    filelist_group.add_argument(
        "-fl",
        "--filelist",
        metavar="FILE",
        help="read file list from FILE",
    )
    filelist_group.add_argument(
        "-lfl",
        "--lastfilelist",
        action="store_true",
        help="use the last generated file list",
    )
    p.add_argument(
        "--resume",
        action="store_true",
        help="resume an interrupted scan using the last generated hash file",
    )
    p.set_defaults(func=cmd_hashscan)

    # -----------------------------------------------------------------------
    # hashwrite
    # -----------------------------------------------------------------------

    p = subparsers.add_parser(
        "hashwrite",
        help="Write hash values to audio file tags.",
        description="Write hash values to audio file tags.",
    )
    p.add_argument("hashfile", help="hash file")
    p.set_defaults(func=cmd_hashwrite)

    # -----------------------------------------------------------------------
    # match
    # -----------------------------------------------------------------------

    p = subparsers.add_parser(
        "match",
        help="Find matching entries between hash files.",
        description="Find matching entries between hash files.",
    )
    p.add_argument("hashfile1", help="first hash file")
    p.add_argument("hashfile2", help="second hash file")
    p.set_defaults(func=cmd_match)

    # -----------------------------------------------------------------------
    # merge
    # -----------------------------------------------------------------------

    p = subparsers.add_parser(
        "merge",
        help="Merge multiple hash files.",
        description="Merge multiple hash files.",
    )
    p.add_argument("hashfile1", help="first hash file")
    p.add_argument("hashfile2", help="second hash file")
    p.set_defaults(func=cmd_merge)

    # -----------------------------------------------------------------------
    # move
    # -----------------------------------------------------------------------

    p = subparsers.add_parser(
        "move",
        help="Move files based on a hash file.",
        description="Move files based on a hash file.",
    )
    p.add_argument("hashfile", help="hash file")
    p.set_defaults(func=cmd_move)

    # -----------------------------------------------------------------------
    # remux
    # -----------------------------------------------------------------------

    p = subparsers.add_parser(
        "remux",
        help="Remux FLAC audio containers.",
        description="Remux FLAC audio containers.",
    )
    p.add_argument("hashfile", help="hash file")
    p.set_defaults(func=cmd_remux)

    # -----------------------------------------------------------------------
    # sort
    # -----------------------------------------------------------------------

    p = subparsers.add_parser(
        "sort",
        help="Sort a hash file.",
        description="Sort a hash file.",
    )
    p.add_argument("hashfile", help="hash file")
    p.set_defaults(func=cmd_sort)

    # -----------------------------------------------------------------------
    # stats
    # -----------------------------------------------------------------------

    p = subparsers.add_parser(
        "stats",
        help="Detect and count audio files.",
        description="Detect and count audio files.",
    )
    filelist_group = p.add_mutually_exclusive_group()
    filelist_group.add_argument(
        "-fl",
        "--filelist",
        metavar="FILE",
        help="read file list from FILE",
    )
    filelist_group.add_argument(
        "-hl",
        "--hashlist",
        metavar="FILE",
        help="read hash list from FILE",
    )
    filelist_group.add_argument(
        "-lfl",
        "--lastfilelist",
        action="store_true",
        help="use the last generated file list",
    )
    filelist_group.add_argument(
        "-lhl",
        "--lasthashlist",
        action="store_true",
        help="use the last generated hash list",
    )
    p.set_defaults(func=cmd_stats)

    # -----------------------------------------------------------------------
    # tagexport
    # -----------------------------------------------------------------------

    p = subparsers.add_parser(
        "tagexport",
        help="Export tags from audio files.",
        description="Export tags from audio files.",
    )
    p.add_argument("hashfile", help="hash file")
    p.set_defaults(func=cmd_tagexport)

    # -----------------------------------------------------------------------
    # helpall
    # -----------------------------------------------------------------------

    p = subparsers.add_parser(
        "helpall",
        help="Show help for all commands.",
        description="Show help for all commands.",
    )
    p.set_defaults(func=cmd_helpall, parser=parser)

    return parser


# ===========================================================================
# main
# ===========================================================================


def main():

    parser = build_parser()

    if len(sys.argv) == 1:
        parser.print_help()
        return 0

    args = parser.parse_args()
    args.func(args)
    return 0


# ===========================================================================
# entry
# ===========================================================================

if __name__ == "__main__":
    raise SystemExit(main())
