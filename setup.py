from pathlib import Path

from setuptools import find_packages, setup


with Path("requirements.txt").open() as requirements_file:
    install_requires = [line.strip() for line in requirements_file if line.strip() and not line.startswith("#")]

setup(
    name="higher_pleasures",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=install_requires,
    python_requires=">=3.11",
)
