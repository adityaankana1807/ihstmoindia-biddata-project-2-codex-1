from pathlib import Path
import zipfile

root=Path(__file__).resolve().parents[1]
out=root.parent/'I-HSTMO-India-Complete-Project.zip'
excluded={'.build-venv','build','__pycache__','.git'}
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(root.rglob('*')):
        if p.is_file() and not any(part in excluded for part in p.relative_to(root).parts) and p.suffix not in {'.pyc','.log'}:
            z.write(p,Path('ihstmo_india')/p.relative_to(root))
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    assert 'ihstmo_india/dist/I-HSTMO-India.exe' in z.namelist()
    print(f'{out}: {len(z.namelist())} files, {out.stat().st_size:,} bytes; archive verified')
