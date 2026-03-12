"""CLI entry point for gdcpps."""

from __future__ import annotations

import argparse

import build as build_cmd
import deps as deps_cmd
import doctor as doctor_cmd
import init as init_cmd
import render_profile as render_profile_cmd
import run as run_cmd


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gdcpps",
        description="Godot CPP Scaffold tooling.",
    )
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser(
        "init",
        help="Create a new scaffolded client project.",
    )
    init_parser.add_argument("name", help="Project name.")
    init_parser.add_argument(
        "--dir",
        dest="project_dir",
        default=None,
        help="Output directory. Defaults to the project name in the current directory.",
    )

    deps_parser = subparsers.add_parser(
        "deps",
        help="Materialize pinned Godot and godot-cpp dependencies for a scaffolded project.",
    )
    deps_subparsers = deps_parser.add_subparsers(dest="deps_command")
    deps_sync_parser = deps_subparsers.add_parser(
        "sync",
        help="Clone or update pinned source dependencies for a project.",
    )
    deps_sync_parser.add_argument("project_dir", help="Path to the scaffolded project.")
    deps_sync_parser.add_argument(
        "--godot-source",
        dest="godot_source",
        default=None,
        help="Override the Godot source remote with a local path or alternate URL.",
    )
    deps_sync_parser.add_argument(
        "--godot-cpp-source",
        dest="godot_cpp_source",
        default=None,
        help="Override the godot-cpp source remote with a local path or alternate URL.",
    )

    build_parser = subparsers.add_parser(
        "build",
        help="Build a scaffolded project for a given mode and platform.",
    )
    build_parser.add_argument("mode", help="Build mode, currently debug or release.")
    build_parser.add_argument("platform", help="Target platform, currently linux, windows, or web.")
    build_parser.add_argument(
        "--project",
        dest="project_dir",
        default=".",
        help="Path to the scaffolded project. Defaults to the current directory.",
    )

    render_profile_parser = subparsers.add_parser(
        "render-profile",
        help="Generate a Godot SCons profile from a gdcpps project manifest.",
    )
    render_profile_parser.add_argument("project_dir", help="Path to the scaffolded project.")
    render_profile_parser.add_argument("platform", help="Target platform name.")
    render_profile_parser.add_argument(
        "--out",
        dest="out_path",
        default=None,
        help="Optional output file path. Defaults to .gdcpps/generated/<platform>.profile.py.",
    )

    subparsers.add_parser(
        "doctor",
        help="Check host tools and environment variables relevant to gdcpps.",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Run a built scaffolded project.",
    )
    run_parser.add_argument("mode", help="Run mode, currently debug or release.")
    run_parser.add_argument("platform", help="Target platform, currently linux or windows.")
    run_parser.add_argument(
        "--project",
        dest="project_dir",
        default=".",
        help="Path to the scaffolded project. Defaults to the current directory.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "init":
            return init_cmd.run(args.name, args.project_dir)
        if args.command == "deps" and args.deps_command == "sync":
            return deps_cmd.run(args.project_dir, args.godot_source, args.godot_cpp_source)
        if args.command == "build":
            return build_cmd.run(args.project_dir, args.mode, args.platform)
        if args.command == "render-profile":
            return render_profile_cmd.run(args.project_dir, args.platform, args.out_path)
        if args.command == "doctor":
            return doctor_cmd.run()
        if args.command == "run":
            return run_cmd.run(args.project_dir, args.mode, args.platform)
    except Exception as exc:
        print(f"error: {exc}")
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
