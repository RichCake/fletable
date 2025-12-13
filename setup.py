from setuptools import find_packages, setup


def readme():
    with open("README.md", "r") as f:
        return f.read()


setup(
    name="fletable",
    version="0.0.1",
    author="RichCake",
    author_email="abs2016123@gmail.com",
    description="Tables that take data from SQL database",
    long_description=readme(),
    long_description_content_type="text/markdown",
    url="your_url",
    packages=find_packages(),
    install_requires=["requests>=2.25.1"],
    classifiers=[
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    keywords="files speedfiles ",
    project_urls={"GitHub": "your_github"},
    python_requires=">=3.6",
)
