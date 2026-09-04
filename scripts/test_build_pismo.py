"""Unit tests for build_pismo.py — the I/O-facing half left after build_pismo_logic.py
was extracted (see its module docstring for the pure functions, which get doctests
instead of tests here).

Every external binary (pandoc, weasyprint, Chrome, wkhtmltopdf, pdfinfo, pdffonts) is
mocked via shutil.which / subprocess.run — none of them need to be installed to run
this suite.
"""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import build_pismo


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
                ["pandoc", "-f", "markdown", "-t", "html5", path],
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
        with (
            mock.patch(
                "build_pismo.shutil.which", side_effect=lambda n: which_map.get(n)
            ),
            mock.patch("build_pismo.subprocess.run", side_effect=run_side_effect),
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
