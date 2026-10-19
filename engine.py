"""Polaroid geometry and image processing. Coordinates use pixel edges."""
import io
import math
import re
import unicodedata
from PIL import Image, ImageCms, ImageEnhance, ImageOps

DPI = 300
PHOTO = 945
PAGE = (1500, 1063)
APERTURE = (70, 59, 1015, 1004)
RED_START = 1295
SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))
DEFAULTS = dict(cx=.5, cy=.5, zoom=1, rotation=270, mode='contain', brightness=1,
                contrast=1, saturation=1, sharpness=1)


def load_image(data):
    with Image.open(io.BytesIO(data)) as source:
        if source.width * source.height > 60_000_000:
            raise ValueError('A imagem excede 60 megapixels.')
        source.load()
        image = ImageOps.exif_transpose(source) if source.getexif().get(274, 1) != 1 else source
        profile = source.info.get('icc_profile')
        alpha = image.convert('RGBA').getchannel('A') if image.mode in ('RGBA', 'LA', 'P') else None
        if profile:
            try:
                color = image.convert('RGB') if image.mode in ('RGBA', 'LA', 'P') else image
                image = ImageCms.profileToProfile(color, ImageCms.ImageCmsProfile(io.BytesIO(profile)), SRGB, outputMode='RGB')
            except (ValueError, OSError, ImageCms.PyCMSError):
                image = image.convert('RGB')
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        if alpha is not None:
            background = Image.new('RGB', image.size, 'white')
            background.paste(image, mask=alpha)
            image = background
        return image.copy() if image is source else image


def normalized_edits(edits=None):
    if edits is None:
        edits = {}
    if not isinstance(edits, dict):
        raise ValueError('Ajustes inválidos.')
    result = DEFAULTS.copy()
    for key, low, high in [('cx', 0, 1), ('cy', 0, 1), ('zoom', 1, 5),
                           ('brightness', 0, 2), ('contrast', 0, 2), ('saturation', 0, 2), ('sharpness', 0, 3)]:
        value = float(edits.get(key, result[key]))
        if not math.isfinite(value):
            raise ValueError('Ajustes inválidos.')
        result[key] = max(low, min(high, value))
    rotation = float(edits.get('rotation', 270))
    if rotation not in (0, 90, 180, 270):
        raise ValueError('Rotação inválida.')
    result['rotation'] = int(rotation)
    result['mode'] = edits.get('mode', 'contain')
    if result['mode'] not in ('contain', 'cover'):
        raise ValueError('Encaixe inválido.')
    if result['mode'] == 'contain':
        result['zoom'] = 1
    return result


def oriented(source, rotation):
    return source.transpose({90: Image.Transpose.ROTATE_270,
                             180: Image.Transpose.ROTATE_180, 270: Image.Transpose.ROTATE_90}[rotation]) if rotation else source.copy()


def prepare_photo(source, edits=None):
    edits = normalized_edits(edits)
    image = oriented(source, edits['rotation'])
    if edits['mode'] == 'contain':
        image = ImageOps.contain(image, (PHOTO, PHOTO), Image.Resampling.LANCZOS)
        x = round((PHOTO - image.width) * edits['cx'])
        y = round((PHOTO - image.height) * edits['cy'])
    else:
        width, height = image.size
        side = min(width, height) / edits['zoom']
        cx = max(side / 2, min(width - side / 2, edits['cx'] * width))
        cy = max(side / 2, min(height - side / 2, edits['cy'] * height))
        image = image.resize((PHOTO, PHOTO), Image.Resampling.LANCZOS,
                             box=(cx-side/2, cy-side/2, cx+side/2, cy+side/2))
        x = y = 0
    for key, enhancer in [('brightness', ImageEnhance.Brightness), ('contrast', ImageEnhance.Contrast),
                           ('saturation', ImageEnhance.Color), ('sharpness', ImageEnhance.Sharpness)]:
        if edits[key] != 1:
            image = enhancer(image).enhance(edits[key])
    square = Image.new('RGB', (PHOTO, PHOTO), 'white')
    square.paste(image, (x, y))
    return square


def render_tile(source, edits=None):
    page = Image.new('RGB', PAGE, 'white')
    page.paste(prepare_photo(source, edits), APERTURE[:2])
    page.paste((255, 0, 0), (RED_START, 0, PAGE[0], PAGE[1]))
    return page


def jpeg_bytes(image):
    stream = io.BytesIO()
    image.save(stream, 'JPEG', quality=100, subsampling=0, dpi=(DPI, DPI), icc_profile=SRGB.tobytes())
    return stream.getvalue()


def output_names(names):
    used, result = set(), []
    for name in names:
        stem = str(name).replace('\\', '/').rsplit('/', 1)[-1].rsplit('.', 1)[0]
        stem = unicodedata.normalize('NFC', stem)
        stem = re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', stem).strip(' .')[:120] or 'Foto'
        candidate, n = f'{stem}-polaroid.jpg', 2
        while candidate.casefold() in used:
            candidate = f'{stem}-polaroid-{n}.jpg'
            n += 1
        used.add(candidate.casefold())
        result.append(candidate)
    return result


def effective_dpi(size, edits):
    edits = normalized_edits(edits)
    pixels = max(size) if edits['mode'] == 'contain' else min(size) / edits['zoom']
    return round(pixels / PHOTO * DPI)
