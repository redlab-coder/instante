"""Portable batches: originals and validated edits in a bounded ZIP container."""
import hashlib
import json
import zipfile
from engine import normalized_edits

MAX_PHOTOS = 100
MAX_FILE = 50 * 1024**2
MAX_TOTAL = 4 * 1024**3


def write_project(stream, records):
    manifest = {'application': 'PolaroidEditor', 'format': 1, 'photos': []}
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_STORED) as archive:
        for index, (record, meta) in enumerate(records):
            filename = f'photos/{index:04d}.bin'
            with record.original.open('rb') as file:
                digest = hashlib.file_digest(file, 'sha256').hexdigest()
            archive.write(record.original, filename)
            manifest['photos'].append({'file': filename, 'sha256': digest,
                                       'name': meta['name'], 'edits': normalized_edits(meta.get('edits')),
                                       'reviewed': bool(meta.get('reviewed')), 'manual': bool(meta.get('manual'))})
        archive.writestr('project.json', json.dumps(manifest, ensure_ascii=False))


def read_project(stream, make_record):
    staged = []
    try:
        with zipfile.ZipFile(stream) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_PHOTOS + 1 or len({e.filename for e in entries}) != len(entries):
                raise ValueError('Lote inválido ou com arquivos duplicados.')
            info = archive.getinfo('project.json')
            if info.file_size > 1024**2:
                raise ValueError('Manifesto do lote muito grande.')
            manifest = json.loads(archive.read(info))
            if not isinstance(manifest, dict) or manifest.get('application') not in ('PolaroidEditor', 'Instante') or manifest.get('format') != 1:
                raise ValueError('Este arquivo não é um lote do Polaroid Editor compatível.')
            photos = manifest.get('photos')
            if not isinstance(photos, list) or not 1 <= len(photos) <= MAX_PHOTOS:
                raise ValueError('O lote deve conter entre 1 e 100 fotos.')
            if {e.filename for e in entries} != {'project.json'} | {f'photos/{i:04d}.bin' for i in range(len(photos))}:
                raise ValueError('Estrutura do lote inválida.')
            total = 0
            for index, item in enumerate(photos):
                if not isinstance(item, dict) or item.get('file') != f'photos/{index:04d}.bin':
                    raise ValueError('Referência de foto inválida.')
                info = archive.getinfo(item['file'])
                total += info.file_size
                if not 0 < info.file_size <= MAX_FILE or total > MAX_TOTAL or info.flag_bits & 1:
                    raise ValueError('O lote excede os limites de tamanho ou usa criptografia.')
                edits = normalized_edits(item.get('edits'))
                data = archive.read(info)
                if hashlib.sha256(data).hexdigest() != item.get('sha256'):
                    raise ValueError('Uma foto do lote está incompleta ou alterada.')
                name = item.get('name')
                if not isinstance(name, str) or not 1 <= len(name) <= 512:
                    raise ValueError('Nome de foto inválido.')
                staged.append((make_record(data), {'name': name, 'edits': edits,
                                                  'reviewed': bool(item.get('reviewed')), 'manual': bool(item.get('manual'))}))
        return staged
    except (zipfile.BadZipFile, KeyError, TypeError, UnicodeError) as error:
        raise ValueError('Não foi possível abrir este lote do Polaroid Editor.') from error
