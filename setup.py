from setuptools import find_packages, setup


def readme():
    with open("README.md", "r") as f:
        return f.read()


setup(
    name="fletable",
    version="0.0.2",
    author="RichCake",
    author_email="abs2016123@gmail.com",
    description="Tables that take data from SQL database",
    long_description=readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/RichCake/fletable",
    packages=find_packages(),
    install_requires=[
        "flet==0.28.3",
        "flet-cli==0.28.3",
        "flet-desktop==0.28.3",
        "flet-web==0.28.3",
    ],
    classifiers=[
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    keywords="flet sql table ",
    project_urls={"GitHub": "https://github.com/RichCake/fletable"},
    python_requires=">=3.9",
)
