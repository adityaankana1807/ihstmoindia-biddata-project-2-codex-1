"""Run source parsing, fixture generation, training, evaluation and manifest refresh."""
import subprocess
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from scripts.build_datasets import manifest
for command in [[sys.executable,'scripts/build_datasets.py'],[sys.executable,'-m','ihstmo.evaluate']]:
    subprocess.run(command,cwd=root,check=True)
manifest({2021:52974,2022:65893,2023:86420},840)
subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=root,check=True)
