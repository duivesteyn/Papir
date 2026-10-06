from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="papir",
    version="0.2.2",
    author="Benjamin M. Duivesteyn",
    author_email="duivesteyn@gmail.com",
    packages=find_packages(),
    url="https://github.com/duivesteyn/papir",
    license="MIT",
    description="Beam reading material to your e-reader via API, with correct Author + Title.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=["requests"],
    entry_points={"console_scripts": ["papir=papir.cli:main"]},
    python_requires=">=3.9",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Environment :: Console",
        "Topic :: Utilities",
    ],
)
