"""Make sysconfig report the bundled interpreter's prefix after relocation."""
from pathlib import Path
import runpy
import sys

for path in Path(sys.argv[1]).glob('lib/python*/_sysconfigdata_*.py'):
    values = runpy.run_path(str(path))['build_time_vars']
    prefix = values['prefix']
    if not prefix.startswith('/') or prefix == '/':
        raise ValueError('Unexpected interpreter prefix')
    path.write_text(path.read_text() + '\nimport sys\n' +
                    f'build_time_vars = {{k: v.replace({prefix!r}, sys.prefix) if isinstance(v, str) else v for k, v in build_time_vars.items()}}\n')
    text = path.read_text().replace(prefix, '@NYLOCATION_PREFIX@')
    path.write_text(text)
