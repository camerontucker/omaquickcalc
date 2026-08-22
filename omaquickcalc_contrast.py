#!/usr/bin/env python3
"""Choose readable calculator text for the wallpaper beneath its translucent card."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
RGB_SAMPLE = re.compile(r"^(\d+),(\d+),(\d+)$")


def parse_color(value: str) -> tuple[float, float, float]:
    if not HEX_COLOR.fullmatch(value):
        raise ValueError(f"invalid color: {value}")
    return tuple(int(value[index:index + 2], 16) / 255 for index in (1, 3, 5))


def color_hex(color: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(max(0, min(1, channel)) * 255):02X}" for channel in color)


def composite(
    foreground: tuple[float, float, float],
    opacity: float,
    background: tuple[float, float, float],
) -> tuple[float, float, float]:
    opacity = max(0.0, min(1.0, opacity))
    return tuple(
        foreground[index] * opacity + background[index] * (1 - opacity)
        for index in range(3)
    )


def luminance(color: tuple[float, float, float]) -> float:
    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in color)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(
    first: tuple[float, float, float], second: tuple[float, float, float]
) -> float:
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def sample_wallpaper(args: argparse.Namespace) -> tuple[float, float, float]:
    if args.sample:
        return parse_color(args.sample)

    background = Path(args.background).expanduser() if args.background else (
        Path.home() / ".local/state/omarchy/current/background"
    )
    try:
        background = background.resolve(strict=True)
    except (FileNotFoundError, RuntimeError):
        raise ValueError("wallpaper unavailable") from None

    screen_width = max(1, min(32768, args.screen_width))
    screen_height = max(1, min(32768, args.screen_height))
    x = max(0, min(screen_width - 1, args.x))
    y = max(0, min(screen_height - 1, args.y))
    width = max(1, min(screen_width - x, args.width))
    height = max(1, min(screen_height - y, args.height))
    crop = f"{width}x{height}+{x}+{y}"
    screen = f"{screen_width}x{screen_height}"

    try:
        completed = subprocess.run(
            [
                "magick", str(background), "-auto-orient", "-resize", f"{screen}^",
                "-gravity", "center", "-extent", screen, "-gravity", "NorthWest",
                "-crop", crop, "+repage", "-resize", "1x1!", "-format",
                "%[fx:int(255*r)],%[fx:int(255*g)],%[fx:int(255*b)]", "info:-",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        raise ValueError("wallpaper sampling unavailable") from None

    match = RGB_SAMPLE.fullmatch(completed.stdout.strip())
    if not match:
        raise ValueError("invalid wallpaper sample")
    channels = tuple(int(value) for value in match.groups())
    if any(channel > 255 for channel in channels):
        raise ValueError("invalid wallpaper sample")
    return tuple(channel / 255 for channel in channels)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--screen-width", type=int, default=1)
    value.add_argument("--screen-height", type=int, default=1)
    value.add_argument("--x", type=int, default=0)
    value.add_argument("--y", type=int, default=0)
    value.add_argument("--width", type=int, default=1)
    value.add_argument("--height", type=int, default=1)
    value.add_argument("--background")
    value.add_argument("--sample", help=argparse.SUPPRESS)
    value.add_argument("--scrim", required=True)
    value.add_argument("--scrim-opacity", type=float, required=True)
    value.add_argument("--card", required=True)
    value.add_argument("--card-opacity", type=float, required=True)
    value.add_argument("--light", required=True)
    value.add_argument("--dark", required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        wallpaper = sample_wallpaper(args)
        surface = composite(parse_color(args.scrim), args.scrim_opacity, wallpaper)
        surface = composite(parse_color(args.card), args.card_opacity, surface)
        light = parse_color(args.light)
        dark = parse_color(args.dark)
    except ValueError:
        return 1

    foreground = light if contrast_ratio(light, surface) >= contrast_ratio(dark, surface) else dark
    print(f"{color_hex(foreground)} {color_hex(surface)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
