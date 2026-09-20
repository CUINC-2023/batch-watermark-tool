from __future__ import annotations

import io
import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps

from models.settings import (
    CropSettings,
    LogoSettings,
    OutputProfile,
    PipelineSettings,
    ResizeMode,
    TextSettings,
    WatermarkMode,
)


@dataclass(slots=True)
class SourceMetadata:
    exif: bytes | None = None
    icc_profile: bytes | None = None


@dataclass(slots=True)
class PipelineResult:
    image: Image.Image
    metadata: SourceMetadata


class ImagePipeline:
    """Single source of truth used by both preview and final export."""

    def load(self, path: str | Path) -> PipelineResult:
        with Image.open(path) as source:
            exif = source.info.get("exif")
            icc = source.info.get("icc_profile")
            image = ImageOps.exif_transpose(source).convert("RGBA")
        return PipelineResult(image=image, metadata=SourceMetadata(exif=exif, icc_profile=icc))

    def process(
        self,
        source: Image.Image,
        settings: PipelineSettings,
        profile: OutputProfile | None = None,
        preview_max: tuple[int, int] | None = None,
    ) -> Image.Image:
        image = source.convert("RGBA")
        image = self._crop(image, settings.crop)
        active_profile = profile or settings.export.profiles[0]
        image = self._resize(image, active_profile)
        image = self._apply_logo(image, settings.logo)
        image = self._apply_text(image, settings.text)
        if preview_max:
            image.thumbnail(preview_max, Image.Resampling.LANCZOS)
        return image

    @staticmethod
    def _crop(image: Image.Image, crop: CropSettings) -> Image.Image:
        if not crop.enabled:
            return image
        left, top, right, bottom = crop.normalized_box()
        width, height = image.size
        box = (
            round(left * width),
            round(top * height),
            max(round(right * width), round(left * width) + 1),
            max(round(bottom * height), round(top * height) + 1),
        )
        return image.crop(box)

    @staticmethod
    def _resize(image: Image.Image, profile: OutputProfile) -> Image.Image:
        resize = profile.resize
        if resize.mode == ResizeMode.ORIGINAL:
            return image
        if resize.mode == ResizeMode.PERCENT:
            ratio = max(1, resize.percent) / 100
        else:
            longest = max(image.size)
            ratio = min(1.0, max(1, resize.long_edge) / longest)
        size = (max(1, round(image.width * ratio)), max(1, round(image.height * ratio)))
        return image.resize(size, Image.Resampling.LANCZOS) if size != image.size else image

    def _apply_logo(self, image: Image.Image, config: LogoSettings) -> Image.Image:
        if not config.enabled or not config.path or not Path(config.path).is_file():
            return image
        with Image.open(config.path) as raw:
            logo = raw.convert("RGBA")
        scale_width = max(1, round(image.width * min(max(config.scale, 0.01), 2.0)))
        ratio = scale_width / logo.width
        logo = logo.resize((scale_width, max(1, round(logo.height * ratio))), Image.Resampling.LANCZOS)
        if config.rotation % 360:
            logo = logo.rotate(-config.rotation, expand=True, resample=Image.Resampling.BICUBIC)
        logo = self._opacity(logo, config.opacity)
        canvas = image.copy()
        if config.mode == WatermarkMode.TILE:
            step_x = logo.width + max(0, config.tile_gap)
            step_y = logo.height + max(0, config.tile_gap)
            for row, y in enumerate(range(-logo.height, image.height + logo.height, step_y)):
                offset = step_x // 2 if row % 2 else 0
                for x in range(-logo.width + offset, image.width + logo.width, step_x):
                    canvas.alpha_composite(logo, (x, y))
            return canvas
        if config.mode == WatermarkMode.FREE:
            x = round(config.x * image.width - logo.width / 2)
            y = round(config.y * image.height - logo.height / 2)
        else:
            x, y = self._anchor(config.grid_position, image.size, logo.size, config.margin)
        canvas.alpha_composite(logo, (x, y))
        return canvas

    def _apply_text(self, image: Image.Image, config: TextSettings) -> Image.Image:
        if not config.enabled or not config.text.strip():
            return image
        layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        try:
            font = ImageFont.truetype(config.font_path, config.font_size) if config.font_path else ImageFont.truetype("arial.ttf", config.font_size)
        except OSError:
            font = ImageFont.load_default(size=max(10, config.font_size))
        rgba = ImageColor.getrgb(config.color) + (round(255 * min(max(config.opacity, 0), 1)),)
        bbox = draw.multiline_textbbox((0, 0), config.text, font=font)
        text_size = (bbox[2] - bbox[0], bbox[3] - bbox[1])
        x, y = self._anchor(config.position, image.size, text_size, config.margin)
        draw.multiline_text((x, y), config.text, font=font, fill=rgba)
        return Image.alpha_composite(image, layer)

    @staticmethod
    def _opacity(image: Image.Image, opacity: float) -> Image.Image:
        image = image.copy()
        alpha = image.getchannel("A").point(lambda value: round(value * min(max(opacity, 0), 1)))
        image.putalpha(alpha)
        return image

    @staticmethod
    def _anchor(
        position: str,
        canvas: tuple[int, int],
        item: tuple[int, int],
        margin: int,
    ) -> tuple[int, int]:
        horizontal, vertical = {
            "top-left": ("left", "top"), "top-center": ("center", "top"),
            "top-right": ("right", "top"), "middle-left": ("left", "middle"),
            "center": ("center", "middle"), "middle-right": ("right", "middle"),
            "bottom-left": ("left", "bottom"), "bottom-center": ("center", "bottom"),
            "bottom-right": ("right", "bottom"),
        }.get(position, ("right", "bottom"))
        cw, ch = canvas
        iw, ih = item
        x = margin if horizontal == "left" else (cw - iw) // 2 if horizontal == "center" else cw - iw - margin
        y = margin if vertical == "top" else (ch - ih) // 2 if vertical == "middle" else ch - ih - margin
        return x, y

    def encode(
        self,
        image: Image.Image,
        profile: OutputProfile,
        metadata: SourceMetadata,
        preserve_exif: bool = True,
        preserve_icc: bool = True,
    ) -> bytes:
        fmt = profile.format.upper().replace("JPG", "JPEG")
        output = image
        if fmt == "JPEG":
            background = Image.new("RGB", output.size, "white")
            background.paste(output, mask=output.getchannel("A") if output.mode == "RGBA" else None)
            output = background
        kwargs: dict[str, object] = {}
        if preserve_exif and metadata.exif:
            kwargs["exif"] = metadata.exif
        if preserve_icc and metadata.icc_profile:
            kwargs["icc_profile"] = metadata.icc_profile
        if fmt in {"JPEG", "WEBP"}:
            return self._encode_lossy(output, fmt, profile.quality, profile.max_kb, kwargs)
        stream = io.BytesIO()
        output.save(stream, format=fmt, optimize=True, **kwargs)
        payload = stream.getvalue()
        if profile.max_kb and len(payload) > profile.max_kb * 1024:
            raise ValueError(f"PNG 無法在不降低色彩的情況下符合 {profile.max_kb} KB 限制")
        return payload

    @staticmethod
    def _encode_lossy(
        image: Image.Image,
        fmt: str,
        quality: int,
        max_kb: int,
        kwargs: dict[str, object],
    ) -> bytes:
        limit = max_kb * 1024
        best = b""
        for current in range(min(max(quality, 20), 100), 19, -5):
            stream = io.BytesIO()
            image.save(stream, format=fmt, quality=current, optimize=True, **kwargs)
            best = stream.getvalue()
            if not limit or len(best) <= limit:
                return best
        raise ValueError(f"無法在不縮小像素的情況下符合 {max_kb} KB 限制")


def extension_for(format_name: str) -> str:
    return {"JPEG": ".jpg", "JPG": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(
        format_name.upper(), ".jpg"
    )

