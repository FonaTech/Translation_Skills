# Rights and third-party materials

MIT applies to original code, workflow text and author-owned verification fixtures in this repository, Copyright 2026 Yufeng Zhan. It does not relicense any input document, trademark, photograph, font or third-party excerpt.

Third-party source documents and their translations retain their original rights. Downloaded PDFs, user documents, acquisition logs and private test results are excluded from this distribution. Record source attribution and applicable reuse terms in each document project before redistributing its material.

Author-owned synthetic verification and generated stress fixtures are MIT. No translated demonstrations or source-document collections are bundled. No external font binary or browser runtime is bundled. System font references are fallback names; obtain suitable fonts under their own license.

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
| NumPy (optional training only) | BSD-3-Clause, with additional upstream component notices | License and component notices accompany the separately installed NumPy distribution. |
| scikit-learn (optional structure-head comparison training only) | BSD-3-Clause | [License](https://github.com/scikit-learn/scikit-learn/blob/main/COPYING); numerical tree parameters use original inference code. No library source is bundled. |
| SciPy (optional scikit-learn training dependency) | BSD-3-Clause and included third-party notices | [License](https://github.com/scipy/scipy/blob/main/LICENSE.txt); installed separately for training, unnecessary for inference. |
| jsonschema | MIT | [License](https://github.com/python-jsonschema/jsonschema/blob/main/COPYING) |
| FontTools (optional missing-font-map recovery) | MIT | [License](https://github.com/fonttools/fonttools/blob/main/LICENSE); separately installed. Reference font files are user-supplied, remain under their own terms and are never bundled. |

Optional system tools are separately licensed and must be reviewed with their own distributions: LibreOffice (MPL-2.0 and included component notices), Tesseract (Apache-2.0 plus language-data terms), and platform OCR APIs. Playwright downloads a browser at install time; browser and codec notices are supplied by that browser distribution, not this repository. No legal, medical, financial, or certified-translation warranty is made. Check every dependency's current license and notices before redistribution or deployment, especially the PyMuPDF AGPL/commercial choice.

The native table-cell link network and its original geometric training generator are Copyright 2026 Yufeng Zhan, MIT. The checkpoint contains numerical parameters only. Private development PDFs/annotations are not redistributed. NumPy is required only for retraining; standard-library inference introduces no additional runtime dependency. See the table model card for training provenance and limits.

The optional Chronos Document WebUI download uses the author's [Project_Chronos](https://github.com/FonaTech/Project_Chronos) model. Its weights, source and third-party notices are distributed inside that separate application archive; they are not dependencies of this skill.
