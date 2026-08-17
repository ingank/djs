#!/usr/bin/env python3
"""
djs.py
"""

import re
import shutil
import argparse
import datetime
import hashlib
import subprocess
import threading
import sys
import os
import json
import time
from pathlib import Path
from collections import Counter, defaultdict
from typing import TextIO
from mutagen.flac import FLAC


APP_NAME = "djs.py"
APP_VERSION = "v0.04"
APP_DIR = Path(__file__).resolve().parent
AUDIO_FLAC = ("flac",)
AUDIO_LOSSLESS = ("wav", "aiff", "aifc")
AUDIO_LOSSY = ("mp3",)
AUDIO_EXTENSIONS = AUDIO_FLAC + AUDIO_LOSSY + AUDIO_LOSSLESS
START_TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
START_DIR = Path.cwd().resolve()
START_ARGS = " ".join(sys.argv[1:])
NO_COVER = Path(APP_DIR / "no_cover.png")
SEP = f"{os.sep}"


# ===========================================================================
# core
# ===========================================================================


def stage_directory_name(command: str) -> Path:
    """
    Return the path of the staging directory for *command*.

    The directory name is derived from the current working directory,
    the command name, and the startup timestamp.
    """
    return Path(START_DIR / f".{command}__{START_TIMESTAMP}")


def report_file_name(command: str, format: str) -> Path:
    """
    Return the path of the report file for *command*.

    The file name is derived from the current working directory,
    the command name, and the startup timestamp, using a '.txt'
    extension.
    """
    return Path(START_DIR / f"{command}__{START_TIMESTAMP}__{format}.txt")


def latest_file(fmt: str) -> Path | None:
    files = START_DIR.glob(f"*__*__{fmt}.txt")
    latest = max(files, key=lambda p: p.name.rsplit("__", 2)[1], default=None)
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


def emit_staging_area(path: Path, output: TextIO) -> None:
    emit_comment("Staging Area:", f".{SEP}{path}", output)


def emit_scanning(output: TextIO) -> None:
    emit_comment("Scanning:", "Filesystem", output)


def emit_processing(count: int, output: TextIO) -> None:
    emit_comment("Processing:", f"{count} files", output)


def emit_resuming(count: int, output: TextIO) -> None:
    emit_comment("Resuming:", f"{count} files", output)


def emit_skipping(count: int, output: TextIO) -> None:
    emit_comment("Skipping:", f"{count} directories", output)


def emit_copied_lines(count: int, output: TextIO) -> None:
    emit_comment("Copied:", f"{count} lines", output)


def emit_processed_files(count: int, output: TextIO) -> None:
    emit_comment("Processed:", f"{count} files", output)


def emit_listed(count: int, output: TextIO) -> None:
    emit_comment("Listed:", f"{count} files", output)


def emit_hashed(count: int, output: TextIO) -> None:
    emit_comment("Hashed:", f"{count} files", output)


def emit_duration(seconds: float, output: TextIO) -> None:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds_int = int(seconds % 60)
    hundredths = int((seconds % 1) * 100)
    timetext = f"{hours:02d}:{minutes:02d}:{seconds_int:02d},{hundredths:02d}"
    emit_comment("Duration:", timetext, output)


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


def analyze_audio(file: Path, mode: int) -> tuple[str | None, float | None, float | None]:
    """
    Analyze an audio file using FFmpeg.

    The analysis mode determines which measurements are performed:

        1: Calculate only the SHA-256 hash.
           The hash is computed from normalized PCM audio converted to
           96 kHz, stereo, signed 24-bit little-endian PCM.

        2: Calculate only Integrated Loudness (LUFS) and
           Loudness Range (LRA) using FFmpeg's EBU R 128 / ebur128
           filter.

        3: Calculate the SHA-256 hash, Integrated Loudness (LUFS),
           and Loudness Range (LRA) in a single FFmpeg pass.
           The decoded audio is split into separate hash and
           loudness analysis paths.

    Args:
        file: Path to the input audio file.
        mode: Analysis mode:
            1 for SHA-256 only,
            2 for LUFS/LRA only,
            3 for all measurements.

    Returns:
        A tuple containing:
            - SHA-256 hex digest, or None if not requested.
            - Integrated Loudness in LUFS, or None if not requested.
            - Loudness Range (LRA) in LU, or None if not requested.

    Raises:
        RuntimeError: If the analysis mode is invalid or FFmpeg
            fails to process the input file.
    """
    if mode == 1:
        ffmpeg_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i", str(file),
            "-map", "0:a:0",
            "-vn",
            "-f", "s24le",
            "-acodec", "pcm_s24le",
            "-ar", "96000",
            "-ac", "2",
            "-",
        ]

    elif mode == 2:
        ffmpeg_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i", str(file),
            "-map", "0:a:0",
            "-af", "ebur128=framelog=quiet",
            "-f", "null",
            "-",
        ]

    elif mode == 3:
        ffmpeg_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i", str(file),
            "-filter_complex",
            (
                "[0:a:0]asplit=2[loud][hash];"
                "[loud]ebur128=framelog=quiet,anullsink;"
                "[hash]anull[hashout]"
            ),
            "-map", "[hashout]",
            "-vn",
            "-f", "s24le",
            "-acodec", "pcm_s24le",
            "-ar", "96000",
            "-ac", "2",
            "-",
        ]

    else:
        raise RuntimeError(f"Unknown analyze mode: {mode}")

    proc = subprocess.Popen(
        ffmpeg_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert proc.stdout is not None
    assert proc.stderr is not None

    hasher = hashlib.sha256() if mode in (1, 3) else None
    stderr_chunks: list[bytes] = []

    def drain_stderr() -> None:

        while True:

            chunk = proc.stderr.read(64 * 1024)

            if not chunk:
                break

            stderr_chunks.append(chunk)

    stderr_thread = threading.Thread(
        target=drain_stderr,
        daemon=True,
    )

    stderr_thread.start()

    try:

        if hasher is not None:
            # HASH / ALL: PCM
            for chunk in iter(lambda: proc.stdout.read(1024 * 1024), b""):
                hasher.update(chunk)

        else:
            # LOUDNESS:
            for chunk in iter(lambda: proc.stdout.read(1024 * 1024),  b""):
                pass

    finally:

        proc.stdout.close()

    ret = proc.wait()
    stderr_thread.join()
    stderr = b"".join(stderr_chunks)

    if ret != 0:

        raise RuntimeError(
            f"ffmpeg failed with code {ret} for {file}\n"
            f"{stderr.decode('utf-8', errors='replace')}"
        )

    digest = hasher.hexdigest() if hasher is not None else None

    lufs = None
    lra = None

    if mode in (2, 3):

        stderr_text = stderr.decode("utf-8", errors="replace")
        in_summary = False

        for line in stderr_text.splitlines():

            if "Summary:" in line:
                in_summary = True
                continue

            if not in_summary:
                continue

            if "I:" in line and "LUFS" in line:

                match = re.search(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", line)

                if match:
                    lufs = float(match.group(1))

            elif "LRA:" in line and "LU" in line:

                match = re.search(r"LRA:\s*(-?\d+(?:\.\d+)?)\s*LU", line)

                if match:
                    lra = float(match.group(1))

    return digest, lufs, lra


def ffprobe_json(path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-hide_banner",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False  # -> stdout/stderr as bytes
    )

    assert proc.returncode == 0
    stdout_str = proc.stdout.decode("utf-8", errors="replace")
    return json.loads(stdout_str)


def first_audio_stream(info: dict) -> str | None:
    for _ in info.get("streams", []):
        if _.get("codec_type") == "audio":
            return _.get("codec_name")
    raise RuntimeError()


def first_pic_index(info: dict) -> int:
    for _ in info.get("streams", []):
        if _.get("codec_type") == "video":
            disp = _.get("disposition") or {}
            if disp.get("attached_pic") == 1:
                return (_.get("index"))
    return 0


def touch_flac_comment(path: Path):
    flac_file = FLAC(path)
    if "description" in flac_file:
        flac_file["COMMENT"] = flac_file["description"]
        del flac_file["description"]
        flac_file.save()


def ffmpeg_encode(
        scr: Path,
        dst: Path,
        pic_idx: int | None,
) -> list[str]:

    cmd = [
        "ffmpeg",
        "-v", "error",
        "-i", str(scr),
    ]

    # No embedded cover found: use external placeholder image
    if pic_idx is None:
        cmd += ["-i", str(NO_COVER)]

    # Preserve all metadata; mapping audiostream
    cmd += [
        "-map_metadata", "0",
        "-map", "0:a:0"
    ]

    # Use external placeholder cover
    if pic_idx is None:
        cmd += [
            "-map", "1:v:0",
            "-vf", "scale=600:600"
        ]
    # Use embedded cover: center-crop to square and resize
    else:
        crop = "crop='min(iw,ih)':"
        crop += "'min(iw,ih)':"
        crop += "'(iw-min(iw,ih))/2':"
        crop += "'(ih-min(iw,ih))/2',"
        crop += "scale=600:600"
        cmd += [
            "-map", f"0:{pic_idx}",
            "-vf", crop
        ]

    cmd += ["-disposition:v:0", "attached_pic"]

    ext = scr.suffix.lower().lstrip(".")

    if ext in AUDIO_FLAC:
        audio_args = ["-c:a", "copy"]

    elif ext in AUDIO_LOSSLESS:
        audio_args = ["-c:a", "flac"]

    elif ext in AUDIO_LOSSY:
        audio_args = [
            "-c:a", "flac",
            "-sample_fmt", "s16",
        ]

    else:
        raise RuntimeError()

    cmd += [
        *audio_args,
        "-c:v", "mjpeg",
        "-y", str(dst)
    ]

    proc = subprocess.run(
        cmd, text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr}")


# ===========================================================================
# commands
# ===========================================================================


def cmd_copy(args) -> None:
    latest_find = latest_file("fl")
    latest_hashscan = latest_file("hl")

    rep_file = report_file_name("copy", "log").open("w", encoding="utf-8")
    emit_header(rep_file)

    if args.filelist:
        filelist = Path(args.filelist)
        emit_reading(filelist, rep_file)
        files = parse_filelist(filelist)

    elif args.hashlist:
        hashlist = Path(args.hashliist)
        emit_reading(hashlist, rep_file)
        data = parse_hashlist(hashlist)
        files = {path for _, path in data}

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
        files = [path for _, path in data]

    else:
        emit_scanning(rep_file)
        files, skipped = find_files(START_DIR, AUDIO_EXTENSIONS)
        emit_skipping(len(skipped), rep_file)

    emit_processing(len(files), rep_file)
    stage_dir = stage_directory_name("copy")
    emit_staging_area(stage_dir.relative_to(START_DIR), rep_file)
    stage_dir.mkdir(parents=True, exist_ok=True)
    processed = 0

    for relative_path in files:
        source = Path(START_DIR / relative_path)
        destination = Path(START_DIR / stage_dir / relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        emit_text(f"{relative_path}", rep_file)
        processed += 1

    emit_processed_files(processed, rep_file)
    emit_footer(rep_file)
    rep_file.close()


def cmd_diff(args):
    print(f"Dummy: diff ({args.hashfile1}, {args.hashfile2})")


def cmd_dupes(args):
    print("Dummy: dupes")


def cmd_encode(args):
    rep_file = report_file_name("encode", "log").open("w", encoding="utf-8")
    emit_header(rep_file)
    emit_scanning(rep_file)
    files, skipped = find_files(START_DIR, AUDIO_EXTENSIONS)
    emit_skipping(len(skipped), rep_file)
    emit_processing(len(files), rep_file)
    stage_dir = stage_directory_name("encode")
    emit_staging_area(stage_dir.relative_to(START_DIR), rep_file)
    stage_dir.mkdir(parents=True, exist_ok=True)
    processed = 0

    for rel_path in files:
        src = Path(START_DIR / rel_path)
        dst = Path(START_DIR / stage_dir / rel_path.with_suffix(".flac"))
        dst.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg_encode(src, dst, None)
        emit_text(f"{rel_path}", rep_file)
        processed += 1

    emit_processed_files(processed, rep_file)
    emit_footer(rep_file)
    rep_file.close()


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
    report_file = report_file_name("find", "fl").open("w", encoding="utf-8")
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
    start_time = time.perf_counter()

    latest_find = latest_file("fl")
    latest_hashscan = latest_file("hl")
    previous_records: list[tuple[str, Path]] = []

    mode = 3
    mode = 1 if args.hash_only else mode
    mode = 2 if args.loudness_only else mode

    skipped = 0
    copied = 0
    processed = 0

    rep_file = report_file_name("hashscan", "hl").open("w", encoding="utf-8")
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

    for digest, path in previous_records:
        emit_text(f"{digest} {path}", rep_file)
        copied += 1

    for path in files:
        digest, lufs, lra = analyze_audio(START_DIR / path, mode)
        lufs = f"{lufs:5.1f}" if lufs else None
        lra = f"{lra:4.1f}" if lra else None
        emit_text(f"{digest} {lufs} {lra} {path}", rep_file)
        processed += 1

    if copied:
        emit_copied_lines(copied, rep_file)

    emit_processed_files(processed, rep_file)
    emit_duration(time.perf_counter() - start_time, rep_file)
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
    latest_find = latest_file("fl")
    latest_hashscan = latest_file("hl")
    skipped = 0

    rep_file = report_file_name("stats", "log").open("w", encoding="utf-8")
    emit_header(rep_file)

    if args.filelist:
        filelist = Path(args.filelist)
        emit_reading(filelist, rep_file)
        files = parse_filelist(filelist)

    elif args.hashlist:
        hashlist = Path(args.hashliist)
        emit_reading(hashlist, rep_file)
        data = parse_hashlist(hashlist)
        files = {path for _, path in data}

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
        emit_text(f"   .{SEP}{directory}: {line}", rep_file)

    if skipped:
        emit_text(f"Skipped directories: {len(skipped)}", rep_file)
        for directory in sorted(skipped):
            emit_text(f"   .{SEP}{directory}", rep_file)

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
        help="Copy files based on a file.",
        description="Copy files based on a file.",
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
