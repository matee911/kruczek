"""podmiot.sh: rejestr oddający HTML zamiast JSON-a (przerwa techniczna) to czytelny błąd, nie „jq: parse error”."""

import os
import shutil
import subprocess
from pathlib import Path

KORZEN = Path(__file__).resolve().parent.parent
SKRYPT = KORZEN / "scripts" / "podmiot.sh"

HTML_PRZERWY = "<!DOCTYPE html>\n<html><head><title>Przerwa techniczna</title></head>\n<body>Przerwa techniczna</body></html>"
JSON_MF = '{"result":{"subject":{"name":"Firma Testowa sp. z o.o.","nip":"5252344078","krs":"0000240611"}}}'
JSON_KRS = '{"odpis":{"dane":{"dzial1":{"danePodmiotu":{"nazwa":"FIRMA TESTOWA SP. Z O.O."}}}}}'


def _uruchom(tmp_path, *argumenty, krs=JSON_KRS, mf=JSON_MF, kod_krs=0):
    # Atrapa curl: odpowiedź i kod wyjścia per rejestr ustawia test (22 = curl -f przy HTTP >= 400).
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (tmp_path / "mf.txt").write_text(mf)
    (tmp_path / "krs.txt").write_text(krs)
    curl = bin_dir / "curl"
    curl.write_text(
        "#!/bin/sh\n"
        f'case "$*" in *api-krs*) cat "{tmp_path}/krs.txt"; exit {kod_krs} ;; '
        f'*) cat "{tmp_path}/mf.txt" ;; esac\n'
    )
    curl.chmod(0o755)
    (bin_dir / "jq").symlink_to(shutil.which("jq"))
    return subprocess.run(
        ["/bin/bash", str(SKRYPT), *argumenty],
        env={"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )


def test_krs_w_przerwie_technicznej_to_czytelny_blad(tmp_path):
    # Arrange / Act
    wynik = _uruchom(tmp_path, "krs", "0000240611", "P", krs=HTML_PRZERWY)

    # Assert
    assert wynik.returncode == 1
    assert "KRS" in wynik.stderr
    assert "nie jest JSON-em" in wynik.stderr
    assert "parse error" not in wynik.stderr


def test_biala_lista_w_przerwie_technicznej_to_czytelny_blad(tmp_path):
    # Arrange / Act
    wynik = _uruchom(tmp_path, "nip", "5252344078", mf=HTML_PRZERWY)

    # Assert
    assert wynik.returncode == 1
    assert "Biała lista VAT" in wynik.stderr
    assert "parse error" not in wynik.stderr


def test_blad_curl_zachowuje_swoj_kod(tmp_path):
    # Arrange — np. przeniesiony endpoint (404): smoketest ma to widzieć jako awarię, nie jako „ok”.
    # Act
    wynik = _uruchom(tmp_path, "krs", "0000240611", "P", krs="", kod_krs=22)

    # Assert
    assert wynik.returncode == 22


def test_krs_z_poprawnym_json_dziala_jak_dotad(tmp_path):
    # Arrange / Act
    wynik = _uruchom(tmp_path, "krs", "0000240611", "P")

    # Assert
    assert wynik.returncode == 0, wynik.stderr
    assert "FIRMA TESTOWA SP. Z O.O." in wynik.stdout


def test_pelny_bez_krs_oddaje_biala_liste_z_notka(tmp_path):
    # Arrange / Act
    wynik = _uruchom(tmp_path, "pelny", "5252344078", krs=HTML_PRZERWY)

    # Assert
    assert wynik.returncode == 0, wynik.stderr
    assert "Firma Testowa sp. z o.o." in wynik.stdout
    assert "KRS niedostępny" in wynik.stdout
    assert "podmiot.sh krs 0000240611" in wynik.stdout


def test_skrypt_jest_wykonywalny():
    # Arrange / Act / Assert
    assert os.access(SKRYPT, os.X_OK)
