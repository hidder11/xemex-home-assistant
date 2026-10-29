"""Guard the public repository's HACS custom-integration packaging."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'https://github.com/hidder11/xemex-home-assistant'


def test_hacs_manifest_selects_standard_integration_directory():
    manifest = json.loads((ROOT / 'hacs.json').read_text())
    assert manifest['name'] == 'Xemex Home Assistant Integration'
    assert manifest['content_in_root'] is False
    assert manifest['hide_default_branch'] is False
    assert manifest['zip_release'] is False
    assert [p.name for p in (ROOT / 'custom_components').iterdir()
            if p.is_dir() and p.name != '__pycache__'] == ['xemex']


def test_integration_has_required_hacs_metadata():
    manifest = json.loads((ROOT / 'custom_components/xemex/manifest.json').read_text())
    assert manifest['documentation'] == REPOSITORY
    assert manifest['issue_tracker'] == REPOSITORY + '/issues'
    assert manifest['codeowners'] == ['@hidder11']
    assert manifest['domain'] == 'xemex'
    assert manifest['version']
    assert (ROOT / 'custom_components/xemex/brand/icon.png').is_file()


def test_hacs_manifest_is_not_ignored():
    import subprocess
    if not (ROOT / '.git').exists():
        return  # Source archives have no Git index or ignore command context.
    result = subprocess.run(['git', 'check-ignore', '--quiet', 'hacs.json'], cwd=ROOT)
    assert result.returncode == 1
