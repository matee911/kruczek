"""Unit tests for build_pismo.py — the I/O-facing half left after build_pismo_logic.py
was extracted (see its module docstring for the pure functions, which get doctests
instead of tests here).

Every external binary (pandoc, weasyprint, Chrome, wkhtmltopdf, pdfinfo, pdffonts) is
mocked via shutil.which / subprocess.run — none of them need to be installed to run
this suite.
"""

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import build_pismo
import build_pismo_logic


def run_main(argv):
    """Call build_pismo.main() with the given argv, return (stdout, exit_code).

    `exit_code` is main()'s SystemExit.code verbatim (0 on a clean return) — for the
    error paths in this module that's a human-readable string, not an int, so tests
    that care about the message assert on it directly instead of going through
    stdout (sys.exit's argument is never printed here, since we catch it ourselves).
    """
    old_argv = sys.argv
    buf = io.StringIO()
    code = 0
    try:
        sys.argv = ["build_pismo.py", *argv]
        with redirect_stdout(buf):
            try:
                build_pismo.main()
            except SystemExit as e:
                code = e.code
    finally:
        sys.argv = old_argv
    return buf.getvalue(), code


class TestFindChrome(unittest.TestCase):
    def test_returns_none_when_nothing_found(self):
        with (
            mock.patch("build_pismo.shutil.which", return_value=None),
            mock.patch("build_pismo.os.path.exists", return_value=False),
        ):
            self.assertIsNone(build_pismo.find_chrome())

    def test_returns_first_matching_named_binary(self):
        def which(name):
            return "/usr/bin/chromium" if name == "chromium" else None

        with (
            mock.patch("build_pismo.shutil.which", side_effect=which),
            mock.patch("build_pismo.os.path.exists", return_value=False),
        ):
            self.assertEqual(build_pismo.find_chrome(), "/usr/bin/chromium")

    def test_falls_back_to_macos_app_bundle(self):
        mac_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

        with (
            mock.patch("build_pismo.shutil.which", return_value=None),
            mock.patch("build_pismo.os.path.exists", side_effect=lambda p: p == mac_path),
        ):
            self.assertEqual(build_pismo.find_chrome(), mac_path)


class TestRenderMd(unittest.TestCase):
    def test_falls_back_to_escaped_pre_without_pandoc(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.md")
            Path(path).write_text("# Title\n\n<b>not html</b>", encoding="utf-8")
            with mock.patch("build_pismo.shutil.which", return_value=None):
                out = build_pismo.render_md(path)
            self.assertEqual(out, "<pre># Title\n\n&lt;b&gt;not html&lt;/b&gt;</pre>")

    def test_uses_pandoc_and_postprocesses_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.md")
            Path(path).write_text("# Title\n\nSection\n", encoding="utf-8")
            fake_stdout = "<h1>Title</h1>\n<h2>Sub</h2><p>text</p>"
            with (
                mock.patch("build_pismo.shutil.which", return_value="/usr/bin/pandoc"),
                mock.patch(
                    "build_pismo.subprocess.run",
                    return_value=mock.Mock(stdout=fake_stdout),
                ) as run,
            ):
                out = build_pismo.render_md(path)
            run.assert_called_once_with(
                ["pandoc", "-f", "markdown-raw_html", "-t", "html5", path],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertNotIn("<h1>", out)
            self.assertIn("<h4>Sub</h4>", out)


class TestRenderAttachment(unittest.TestCase):
    def test_dispatches_md_to_render_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.md")
            Path(path).write_text("<i>x</i>", encoding="utf-8")
            with mock.patch("build_pismo.shutil.which", return_value=None):
                out = build_pismo.render_attachment(path)
            self.assertEqual(out, "<pre>&lt;i&gt;x&lt;/i&gt;</pre>")

    def test_embeds_image_as_base64(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.png")
            Path(path).write_bytes(b"\x89PNG\r\n\x1a\n fake bytes")
            out = build_pismo.render_attachment(path)
            self.assertTrue(out.startswith('<img src="data:image/png;base64,'))

    def test_wraps_plain_text_in_escaped_pre(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.txt")
            Path(path).write_text("a & b", encoding="utf-8")
            out = build_pismo.render_attachment(path)
            self.assertEqual(out, "<pre>a &amp; b</pre>")

    def test_describes_unknown_binary_with_size_and_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.bin")
            Path(path).write_bytes(b"\x00\x01\x02")
            out = build_pismo.render_attachment(path)
            self.assertIn("a.bin", out)
            self.assertIn("3 B", out)
            self.assertRegex(out, r"[0-9a-f]{64}")


class TestBuildAttachments(unittest.TestCase):
    def test_builds_blocks_list_and_report_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            p1 = os.path.join(tmp, "a.txt")
            p2 = os.path.join(tmp, "b.txt")
            Path(p1).write_text("A", encoding="utf-8")
            Path(p2).write_text("B", encoding="utf-8")
            blocks, lista, zal_info = build_pismo.build_attachments(
                [f"{p1}:Pierwszy", p2]
            )
            self.assertEqual(len(blocks), 2)
            self.assertIn("Załącznik nr 1 — Pierwszy", blocks[0])
            self.assertIn("Załącznik nr 2 — b.txt", blocks[1])
            self.assertEqual(len(lista), 2)
            self.assertIn("Pierwszy", lista[0])
            self.assertEqual([i for i, *_ in zal_info], [1, 2])
            self.assertEqual(zal_info[0][1], "Pierwszy")
            self.assertEqual(zal_info[1][1], "b.txt")

    def test_exits_when_attachment_missing(self):
        with self.assertRaises(SystemExit):
            build_pismo.build_attachments(["/no/such/file.txt"])


def _pdffonts_table(*, unembedded=()):
    """Build a fixed-width `pdffonts` fixture; column alignment computed, not guessed."""
    header = "name".ljust(38) + "type".ljust(18) + "emb"
    sep = "-" * 56
    rows = [
        "Liberation Serif".ljust(38) + "CID TrueType".ljust(18) + "yes",
        *(name.ljust(38) + "TrueType".ljust(18) + "no " for name in unembedded),
    ]
    return "\n".join([header, sep, *rows]) + "\n"


class TestMain(unittest.TestCase):
    def _run_with(self, which_map, run_side_effect, argv):
        # `weasyprint --help` odpowiada pusto (stara wersja bez --allowed-protocols), a Chrome
        # znajdowany jest wyłącznie przez which_map — wynik nie zależy od tego, co stoi na maszynie.
        def run(cmd, **kwargs):
            if cmd[:2] == ["weasyprint", "--help"]:
                return mock.Mock(returncode=0, stdout="", stderr="")
            return run_side_effect(cmd, **kwargs)

        bez_sciezek_bezwzglednych = tuple(
            c for c in build_pismo.CHROME_CANDIDATES if not os.path.isabs(c)
        )
        with (
            mock.patch(
                "build_pismo.shutil.which", side_effect=lambda n: which_map.get(n)
            ),
            mock.patch("build_pismo.CHROME_CANDIDATES", bez_sciezek_bezwzglednych),
            mock.patch("build_pismo.subprocess.run", side_effect=run),
        ):
            return run_main(argv)

    def _run_with_weasyprint(self, argv):
        def run(cmd, **kwargs):
            if cmd[0] == "weasyprint":
                Path(cmd[2]).write_bytes(b"%PDF-1.4 fake")
            return mock.Mock(returncode=0, stdout="", stderr="")

        return self._run_with({"weasyprint": "/usr/bin/weasyprint"}, run, argv)

    def test_builds_pdf_and_reports_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            tpl = os.path.join(tmp, "pismo.html")
            out = os.path.join(tmp, "out.pdf")
            Path(tpl).write_text(
                "<html><!--KRUCZEK:ZALACZNIKI--><!--KRUCZEK:LISTA_ZALACZNIKOW--></html>",
                encoding="utf-8",
            )
            stdout, code = self._run_with_weasyprint([tpl, "-o", out])
            self.assertEqual(code, 0)
            self.assertTrue(os.path.exists(out))
            self.assertFalse(os.path.exists(tpl + ".build.html"))
            self.assertIn("Silnik:    weasyprint", stdout)
            self.assertIn("OK  rozmiar", stdout)

    def test_includes_attachment_in_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            tpl = os.path.join(tmp, "pismo.html")
            out = os.path.join(tmp, "out.pdf")
            zal = os.path.join(tmp, "dowod.txt")
            Path(tpl).write_text(
                "<html><!--KRUCZEK:ZALACZNIKI--><!--KRUCZEK:LISTA_ZALACZNIKOW--></html>",
                encoding="utf-8",
            )
            Path(zal).write_text("treść dowodu", encoding="utf-8")
            stdout, code = self._run_with_weasyprint(
                [tpl, "-o", out, "-z", f"{zal}:Dowód wpłaty"]
            )
            self.assertEqual(code, 0)
            self.assertIn("Dowód wpłaty", stdout)
            self.assertIn("dowod.txt", stdout)

    def test_exits_when_no_engine_available(self):
        # Both shutil.which AND os.path.exists must be forced empty here — find_chrome()
        # falls back to checking real macOS app-bundle paths, which genuinely exist on a
        # dev machine with Chrome installed, and would otherwise make this test invoke a
        # real browser instead of exercising the "no engine" branch.
        with tempfile.TemporaryDirectory() as tmp:
            tpl = os.path.join(tmp, "pismo.html")
            out = os.path.join(tmp, "out.pdf")
            Path(tpl).write_text("<html></html>", encoding="utf-8")
            with (
                mock.patch("build_pismo.shutil.which", return_value=None),
                mock.patch("build_pismo.os.path.exists", return_value=False),
            ):
                _stdout, code = run_main([tpl, "-o", out])
            self.assertNotEqual(code, 0)
            self.assertFalse(os.path.exists(out))

    def test_exits_when_attachment_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tpl = os.path.join(tmp, "pismo.html")
            out = os.path.join(tmp, "out.pdf")
            Path(tpl).write_text("<html></html>", encoding="utf-8")
            _stdout, code = self._run_with_weasyprint(
                [tpl, "-o", out, "-z", "/no/such/file.txt"]
            )
            self.assertIn("brak pliku załącznika", str(code))
            self.assertFalse(os.path.exists(out))

    def test_chrome_engine_success(self):
        def run(cmd, **kwargs):
            flag = next(a for a in cmd if a.startswith("--print-to-pdf="))
            Path(flag.split("=", 1)[1]).write_bytes(b"%PDF-1.4 fake")
            return mock.Mock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            tpl = os.path.join(tmp, "pismo.html")
            out = os.path.join(tmp, "out.pdf")
            Path(tpl).write_text("<html></html>", encoding="utf-8")
            stdout, code = self._run_with(
                {"google-chrome": "/usr/bin/google-chrome"}, run, [tpl, "-o", out]
            )
            self.assertEqual(code, 0)
            self.assertIn("Silnik:    chrome", stdout)

    def test_chrome_engine_failure_exits_with_stderr(self):
        def run(cmd, **kwargs):
            return mock.Mock(returncode=1, stdout="", stderr="boom")

        with tempfile.TemporaryDirectory() as tmp:
            tpl = os.path.join(tmp, "pismo.html")
            out = os.path.join(tmp, "out.pdf")
            Path(tpl).write_text("<html></html>", encoding="utf-8")
            _stdout, code = self._run_with(
                {"google-chrome": "/usr/bin/google-chrome"}, run, [tpl, "-o", out]
            )
            self.assertIn("Chrome/Chromium headless", str(code))
            self.assertIn("boom", str(code))

    def test_wkhtmltopdf_engine_success(self):
        # weasyprint/chrome all resolve to None via which_map, so find_chrome() falls
        # through to checking real macOS app-bundle paths — os.path.exists must be
        # forced False too, or a dev machine with Chrome installed would pick "chrome"
        # instead of "wkhtmltopdf" here.
        def run(cmd, **kwargs):
            Path(cmd[-1]).write_bytes(b"%PDF-1.4 fake")
            return mock.Mock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            tpl = os.path.join(tmp, "pismo.html")
            out = os.path.join(tmp, "out.pdf")
            Path(tpl).write_text("<html></html>", encoding="utf-8")
            with mock.patch("build_pismo.os.path.exists", return_value=False):
                stdout, code = self._run_with(
                    {"wkhtmltopdf": "/usr/bin/wkhtmltopdf"}, run, [tpl, "-o", out]
                )
            self.assertEqual(code, 0)
            self.assertIn("Silnik:    wkhtmltopdf", stdout)

    def test_wkhtmltopdf_engine_failure_exits_with_stderr(self):
        def run(cmd, **kwargs):
            return mock.Mock(returncode=1, stdout="", stderr="wk boom")

        with tempfile.TemporaryDirectory() as tmp:
            tpl = os.path.join(tmp, "pismo.html")
            out = os.path.join(tmp, "out.pdf")
            Path(tpl).write_text("<html></html>", encoding="utf-8")
            with mock.patch("build_pismo.os.path.exists", return_value=False):
                _stdout, code = self._run_with(
                    {"wkhtmltopdf": "/usr/bin/wkhtmltopdf"}, run, [tpl, "-o", out]
                )
            self.assertIn("wkhtmltopdf", str(code))
            self.assertIn("wk boom", str(code))

    def test_reports_sheet_count_and_embedded_fonts(self):
        def run(cmd, **kwargs):
            if cmd[0] == "weasyprint":
                Path(cmd[2]).write_bytes(b"%PDF-1.4 fake")
                return mock.Mock(returncode=0, stdout="", stderr="")
            if cmd[0] == "pdfinfo":
                return mock.Mock(returncode=0, stdout="Pages:          10\n", stderr="")
            if cmd[0] == "pdffonts":
                return mock.Mock(returncode=0, stdout=_pdffonts_table(), stderr="")
            raise AssertionError(f"unexpected command: {cmd}")

        with tempfile.TemporaryDirectory() as tmp:
            tpl = os.path.join(tmp, "pismo.html")
            out = os.path.join(tmp, "out.pdf")
            Path(tpl).write_text("<html></html>", encoding="utf-8")
            stdout, code = self._run_with(
                {
                    "weasyprint": "/usr/bin/weasyprint",
                    "pdfinfo": "/usr/bin/pdfinfo",
                    "pdffonts": "/usr/bin/pdffonts",
                },
                run,
                [tpl, "-o", out],
            )
            self.assertEqual(code, 0)
            self.assertIn("Stron:     10", stdout)
            self.assertIn("OK  10 stron = 5 kartek", stdout)
            self.assertIn("OK  wszystkie fonty osadzone (1)", stdout)
            self.assertNotIn("Popraw powyższe", stdout)

    def test_flags_unembedded_fonts_and_oversized_pdf(self):
        def run(cmd, **kwargs):
            if cmd[0] == "weasyprint":
                Path(cmd[2]).write_bytes(b"%PDF-1.4 " + b"x" * (3 * 1024 * 1024))
                return mock.Mock(returncode=0, stdout="", stderr="")
            if cmd[0] == "pdffonts":
                return mock.Mock(
                    returncode=0, stdout=_pdffonts_table(unembedded=["Arial"]), stderr=""
                )
            raise AssertionError(f"unexpected command: {cmd}")

        with tempfile.TemporaryDirectory() as tmp:
            tpl = os.path.join(tmp, "pismo.html")
            out = os.path.join(tmp, "out.pdf")
            Path(tpl).write_text("<html></html>", encoding="utf-8")
            stdout, code = self._run_with(
                {"weasyprint": "/usr/bin/weasyprint", "pdffonts": "/usr/bin/pdffonts"},
                run,
                [tpl, "-o", out],
            )
            self.assertEqual(code, 0)
            self.assertIn("UWAGA rozmiar", stdout)
            self.assertIn("UWAGA fonty NIEOSADZONE: Arial", stdout)
            self.assertIn("Popraw powyższe", stdout)

    def test_unreadable_pdffonts_header_does_not_fail_the_build(self):
        def run(cmd, **kwargs):
            if cmd[0] == "weasyprint":
                Path(cmd[2]).write_bytes(b"%PDF-1.4 fake")
                return mock.Mock(returncode=0, stdout="", stderr="")
            if cmd[0] == "pdffonts":
                return mock.Mock(returncode=0, stdout="unexpected format\n", stderr="")
            raise AssertionError(f"unexpected command: {cmd}")

        with tempfile.TemporaryDirectory() as tmp:
            tpl = os.path.join(tmp, "pismo.html")
            out = os.path.join(tmp, "out.pdf")
            Path(tpl).write_text("<html></html>", encoding="utf-8")
            stdout, code = self._run_with(
                {"weasyprint": "/usr/bin/weasyprint", "pdffonts": "/usr/bin/pdffonts"},
                run,
                [tpl, "-o", out],
            )
            self.assertEqual(code, 0)
            self.assertIn("nie udało się odczytać nagłówka pdffonts", stdout)
            self.assertNotIn("Popraw powyższe", stdout)


class TestBezpieczenstwoTresci(unittest.TestCase):
    CSP = (
        """<meta http-equiv="Content-Security-Policy" content="default-src 'none'; """
        """style-src 'unsafe-inline'; img-src data:">"""
    )
    SZABLON_PRAWDZIWY = Path(__file__).resolve().parent.parent / "templates" / "pismo.html"

    def _szablon_z_trescia(self, tmp, tresc_html):
        szablon = Path(tmp, "pismo.html")
        szablon.write_text(
            "<body><!--KRUCZEK:TRESC:START--><!--KRUCZEK:TRESC:END-->"
            "<!--KRUCZEK:LISTA_ZALACZNIKOW--><!--KRUCZEK:ZALACZNIKI--></body>",
            encoding="utf-8",
        )
        tresc = Path(tmp, "tresc.html")
        tresc.write_text(tresc_html, encoding="utf-8")
        return szablon, tresc

    def test_tresc_z_obrazkiem_z_pliku_przerywa_budowanie(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Arrange
            szablon, tresc = self._szablon_z_trescia(
                tmp, '<p class="ust">Fakt.</p><img src="file:///etc/hosts">'
            )
            wyjscie = os.path.join(tmp, "p.pdf")
            # Act
            with mock.patch.object(build_pismo, "choose_engine", return_value=None):
                _, kod = run_main([str(szablon), "-o", wyjscie, "--tresc", str(tresc)])
            # Assert
            self.assertIn("niedozwolony", str(kod))
            self.assertFalse(os.path.exists(wyjscie + ".build.html"))

    def test_tresc_z_plikiem_przerywa_przed_zapisem_html_i_pdf(self):
        zle = {
            "obraz z pliku": '<p>a</p><img src="file:///etc/hosts">',
            "obraz z sieci": '<p>a</p><img src="https://example.invalid/p.png">',
            "arkusz z sieci": '<link rel="stylesheet" href="https://example.invalid/a.css"><p>a</p>',
            "styl w atrybucie": '<p style="background:url(https://example.invalid/p.png)">a</p>',
            "ramka": '<iframe src="file:///etc/hosts"></iframe>',
        }
        for nazwa, html in zle.items():
            with self.subTest(nazwa), tempfile.TemporaryDirectory() as tmp:
                # Arrange
                szablon, tresc = self._szablon_z_trescia(tmp, html)
                wyjscie = os.path.join(tmp, "p.pdf")
                # Act
                with mock.patch("build_pismo.subprocess.run") as run:
                    _, kod = run_main(
                        [str(szablon), "-o", wyjscie, "--tresc", str(tresc), "--keep-html"]
                    )
                # Assert
                self.assertIn("niedozwolony", str(kod))
                self.assertFalse(os.path.exists(wyjscie + ".build.html"))
                self.assertFalse(os.path.exists(wyjscie))
                run.assert_not_called()

    def test_html_z_pliku_tresc_ma_csp_szablonu(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Arrange
            tresc = Path(tmp, "tresc.html")
            tresc.write_text('<h1>WEZWANIE</h1><p class="ust">Fakt (zał. 1).</p>', encoding="utf-8")
            wyjscie = os.path.join(tmp, "p.pdf")
            # Act
            with mock.patch.object(build_pismo, "choose_engine", return_value=None):
                run_main([str(self.SZABLON_PRAWDZIWY), "-o", wyjscie, "--tresc", str(tresc), "--keep-html"])
            # Assert
            html = Path(wyjscie + ".build.html").read_text(encoding="utf-8")
            self.assertIn(self.CSP, html)
            self.assertIn('<h1>WEZWANIE</h1><p class="ust">Fakt (zał. 1).</p>', html)

    def test_szablon_blokuje_zasoby_z_plikow_i_sieci(self):
        # Arrange
        szablon = self.SZABLON_PRAWDZIWY.read_text(encoding="utf-8")
        # Assert
        self.assertIn(self.CSP, szablon)

    def test_walidacja_przepuszcza_tresc_ze_wzoru_szablonu(self):
        # Arrange
        szablon = self.SZABLON_PRAWDZIWY.read_text(encoding="utf-8")
        tresc = szablon.split(build_pismo_logic.TRESC_START)[1].split(build_pismo_logic.TRESC_KONIEC)[0]
        # Act / Assert
        build_pismo_logic.sprawdz_tresc(tresc)

    def test_weasyprint_dostaje_allowed_protocols_gdy_go_zna(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Arrange
            tpl, out = os.path.join(tmp, "pismo.html"), os.path.join(tmp, "out.pdf")
            Path(tpl).write_text(
                "<html><body>x<!--KRUCZEK:LISTA_ZALACZNIKOW--><!--KRUCZEK:ZALACZNIKI--></body></html>",
                encoding="utf-8",
            )
            wywolania = []

            def run(cmd, **kwargs):
                wywolania.append(cmd)
                if cmd[:2] == ["weasyprint", "--help"]:
                    return mock.Mock(returncode=0, stdout="  --allowed-protocols <allowed-protocols>", stderr="")
                if cmd[0] == "weasyprint":
                    Path(cmd[2]).write_bytes(b"%PDF-1.4 fake")
                return mock.Mock(returncode=0, stdout="", stderr="")

            # Act
            with (
                mock.patch(
                    "build_pismo.shutil.which",
                    side_effect=lambda n: "/usr/bin/weasyprint" if n == "weasyprint" else None,
                ),
                mock.patch("build_pismo.subprocess.run", side_effect=run),
            ):
                run_main([tpl, "-o", out])
            # Assert
            render = [c for c in wywolania if c[0] == "weasyprint" and "--help" not in c]
            self.assertEqual(render[0][-2:], ["--allowed-protocols", "data"])

    def test_wkhtmltopdf_bez_dostepu_do_plikow_lokalnych(self):
        # Act
        cmd = build_pismo.command_for_engine(
            "wkhtmltopdf",
            out_path="o.pdf",
            tmp_html_path="i.html",
            margins={"T": "25mm", "B": "20mm", "L": "25mm", "R": "20mm"},
        )
        # Assert
        self.assertIn("--disable-local-file-access", cmd)
        self.assertNotIn("--enable-local-file-access", cmd)

    def _chrome(self, run, argv):
        with (
            mock.patch("build_pismo.shutil.which", side_effect=lambda n: None),
            mock.patch("build_pismo.find_chrome", return_value="/usr/bin/chrome"),
            mock.patch("build_pismo.subprocess.run", side_effect=run),
        ):
            return run_main(argv)

    def test_silnik_ktory_wisi_konczy_build_czytelnym_bledem(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Arrange
            tpl, out = os.path.join(tmp, "pismo.html"), os.path.join(tmp, "out.pdf")
            Path(tpl).write_text(
                "<html><body>x<!--KRUCZEK:LISTA_ZALACZNIKOW--><!--KRUCZEK:ZALACZNIKI--></body></html>",
                encoding="utf-8",
            )

            def run(cmd, **kwargs):
                if cmd[0] == "/usr/bin/chrome":
                    raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))
                return mock.Mock(returncode=0, stdout="", stderr="")

            # Act
            _, kod = self._chrome(run, [tpl, "-o", out])
            # Assert
            self.assertIn(f"nie skończył w {build_pismo.LIMIT_SILNIKA_S} s", str(kod))

    def test_weasyprint_bez_flagi_przechodzi_na_chrome(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Arrange
            tpl, out = os.path.join(tmp, "pismo.html"), os.path.join(tmp, "out.pdf")
            Path(tpl).write_text(
                "<html><body>x<!--KRUCZEK:LISTA_ZALACZNIKOW--><!--KRUCZEK:ZALACZNIKI--></body></html>",
                encoding="utf-8",
            )
            wywolania = []

            def run(cmd, **kwargs):
                wywolania.append(cmd)
                if cmd[:2] == ["weasyprint", "--help"]:
                    return mock.Mock(returncode=0, stdout="usage: weasyprint [-h] input output", stderr="")
                if cmd[0] == "/usr/bin/chrome":
                    Path(
                        next(x.split("=", 1)[1] for x in cmd if x.startswith("--print-to-pdf="))
                    ).write_bytes(b"%PDF-1.4 fake")
                return mock.Mock(returncode=0, stdout="", stderr="")

            # Act
            with (
                mock.patch(
                    "build_pismo.shutil.which",
                    side_effect=lambda n: "/usr/bin/weasyprint" if n == "weasyprint" else None,
                ),
                mock.patch("build_pismo.find_chrome", return_value="/usr/bin/chrome"),
                mock.patch("build_pismo.subprocess.run", side_effect=run),
            ):
                stdout, _ = run_main([tpl, "-o", out])
            # Assert
            self.assertIn("Silnik:    chrome", stdout)
            self.assertFalse([c for c in wywolania if c[0] == "weasyprint" and "--help" not in c])


class TestTresc(unittest.TestCase):
    def test_szablon_ma_znaczniki_tresci(self):
        # Arrange
        szablon = (Path(__file__).resolve().parent.parent / "templates" / "pismo.html").read_text(encoding="utf-8")
        # Assert
        self.assertEqual(szablon.count("<!--KRUCZEK:TRESC:START-->"), 1)
        self.assertEqual(szablon.count("<!--KRUCZEK:TRESC:END-->"), 1)

    def test_tresc_z_pliku_trafia_do_html_bez_zmian(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Arrange
            szablon = Path(tmp, "pismo.html")
            szablon.write_text("<body>A<!--KRUCZEK:TRESC:START-->stare<!--KRUCZEK:TRESC:END-->B"
                               "<!--KRUCZEK:LISTA_ZALACZNIKOW--><!--KRUCZEK:ZALACZNIKI--></body>", encoding="utf-8")
            tresc = Path(tmp, "tresc.html")
            tresc.write_text('<h1>WEZWANIE</h1><p class="ust">Fakt (zał. 1).</p>', encoding="utf-8")
            wyjscie = os.path.join(tmp, "p.pdf")
            # Act
            with mock.patch.object(build_pismo, "choose_engine", return_value=None):
                run_main([str(szablon), "-o", wyjscie, "--tresc", str(tresc), "--keep-html"])
            # Assert
            html = Path(wyjscie + ".build.html").read_text(encoding="utf-8")
            self.assertIn('A<!--KRUCZEK:TRESC:START--><h1>WEZWANIE</h1><p class="ust">Fakt (zał. 1).</p>'
                          '<!--KRUCZEK:TRESC:END-->B', html)
            self.assertNotIn("stare", html)

    def test_szablon_bez_znacznikow_tresci_konczy_sie_bledem(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Arrange
            szablon = Path(tmp, "pismo.html")
            szablon.write_text("<body>bez znaczników</body>", encoding="utf-8")
            tresc = Path(tmp, "tresc.html")
            tresc.write_text("<h1>WEZWANIE</h1>", encoding="utf-8")
            # Act
            _, kod = run_main([str(szablon), "-o", os.path.join(tmp, "p.pdf"), "--tresc", str(tresc)])
            # Assert
            self.assertIn("szablon nie ma znaczników treści", str(kod))

    def test_brak_pliku_z_trescia_to_czytelny_blad_a_nie_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Arrange
            szablon = Path(tmp, "pismo.html")
            szablon.write_text("<body>A<!--KRUCZEK:TRESC:START--><!--KRUCZEK:TRESC:END-->B</body>", encoding="utf-8")
            brak = os.path.join(tmp, "nie-ma.html")
            # Act
            _, kod = run_main([str(szablon), "-o", os.path.join(tmp, "p.pdf"), "--tresc", brak])
            # Assert
            self.assertEqual(kod, f"BŁĄD: brak pliku {brak}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
