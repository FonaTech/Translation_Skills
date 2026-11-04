# Rights and third-party materials

MIT applies to original code, workflow text and author-owned demonstration fixtures in this repository, Copyright 2026 Yufeng Zhan. It does not relicense any input document, trademark, photograph, font or third-party excerpt.

Public-PDF validation acquired a W3C dummy PDF, a US IRS W-9 PDF and a US National Archives historical manuscript PDF from their original hosts. Raw PDFs and full page images are not redistributed here. URLs, retrieval metadata, hashes, processing statistics and very short attributed translated excerpts are included only to document tests. Inspect each provider's terms before redistributing or reusing its material. Links/download availability and source revisions can change.

Author-owned synthetic text, paired examples and generated stress fixtures are MIT. Health/legal/financial examples are fictional fixtures, not instructions for real decisions. No external font binary or browser runtime is bundled. System font references are fallback names; obtain suitable fonts under their own license.

Runtime dependencies are installed separately. Their licenses remain in force; the repository MIT license does not relicense them. No third-party Python source, browser, OCR engine, font, or binary is vendored.

| Direct dependency | Upstream license | Notice |
|---|---|---|
| PyMuPDF / MuPDF | AGPL-3.0-or-later or Artifex commercial license | [License terms](https://pymupdf.readthedocs.io/en/latest/about.html#license) |
| Playwright for Python | Apache-2.0 | [License](https://github.com/microsoft/playwright-python/blob/main/LICENSE) |
| PyYAML | MIT | [License](https://github.com/yaml/pyyaml/blob/main/LICENSE) |
| Pillow | HPND (with bundled component notices in its upstream distribution) | [License and notices](https://github.com/python-pillow/Pillow/blob/main/LICENSE) |
| pypdf | BSD-3-Clause | [License](https://github.com/py-pdf/pypdf/blob/main/LICENSE) |
| pdfplumber | MIT | [License](https://github.com/jsvine/pdfplumber/blob/stable/LICENSE.txt) |
| python-docx | MIT | [License](https://github.com/python-openxml/python-docx/blob/master/LICENSE) |
| python-pptx (optional fixtures) | MIT | [License](https://github.com/scanny/python-pptx/blob/master/LICENSE) |
| openpyxl (optional fixtures) | MIT/Expat | [License information](https://openpyxl.readthedocs.io/en/stable/) |
| NumPy (optional training only) | BSD-3-Clause, with additional upstream component notices | License and component notices accompany the separately installed NumPy distribution. |
| jsonschema | MIT | [License](https://github.com/python-jsonschema/jsonschema/blob/main/COPYING) |

Optional system tools are separately licensed and must be reviewed with their own distributions: LibreOffice (MPL-2.0 and included component notices), Tesseract (Apache-2.0 plus language-data terms), and platform OCR APIs. Playwright downloads a browser at install time; browser and codec notices are supplied by that browser distribution, not this repository. No legal, medical, financial, or certified-translation warranty is made. Check every dependency's current license and notices before redistribution or deployment, especially the PyMuPDF AGPL/commercial choice.
