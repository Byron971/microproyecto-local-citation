#!/usr/bin/env python
"""Empaquetamiento del modelo de recomendación local de citas."""

from pathlib import Path

from setuptools import find_packages, setup

NAME = "modelo-citas"
DESCRIPTION = "Recomendador local de citas académicas: TF-IDF + reordenador lineal."
URL = "https://github.com/Byron971/microproyecto-local-citation"
EMAIL = "duquelugocarlos@gmail.com"
AUTHOR = "Equipo microproyecto-local-citation"
REQUIRES_PYTHON = ">=3.14"

ROOT_DIR = Path(__file__).resolve().parent
REQUIREMENTS_DIR = ROOT_DIR / "requirements"
PACKAGE_DIR = ROOT_DIR / "modelo_citas"

# La versión vive en un solo archivo, compartido con modelo_citas.__version__.
with open(PACKAGE_DIR / "VERSION", encoding="utf-8") as version_file:
    VERSION = version_file.read().strip()

with open(ROOT_DIR / "README.md", encoding="utf-8") as readme_file:
    LONG_DESCRIPTION = readme_file.read()


def list_reqs(file_name="requirements.txt"):
    """Dependencias de ejecución, tomadas del archivo de requerimientos."""
    with open(REQUIREMENTS_DIR / file_name, encoding="utf-8") as requirements_file:
        return [
            line.strip()
            for line in requirements_file
            if line.strip() and not line.startswith("#")
        ]


setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author=AUTHOR,
    author_email=EMAIL,
    python_requires=REQUIRES_PYTHON,
    url=URL,
    packages=find_packages(exclude=("tests",)),
    package_data={
        "modelo_citas": ["VERSION", "config.yml"],
        "modelo_citas.trained": ["*.pkl"],
    },
    install_requires=list_reqs(),
    include_package_data=True,
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.14",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
)
