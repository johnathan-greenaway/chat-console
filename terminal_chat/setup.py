from setuptools import setup, find_packages
import os

# Read the contents of README.md
with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

# Read version from app/__init__.py
with open(os.path.join("app", "__init__.py"), "r", encoding="utf-8") as f:
    for line in f:
        if line.startswith("__version__"):
            version = line.split("=")[1].strip().strip('"').strip("'")
            break

setup(
    name="terminal-chat",
    version=version,
    author="Your Name",
    author_email="your.email@example.com",
    description="A terminal-based chat application for LLMs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/terminal-chat",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "textual>=0.11.1",
        "typer>=0.7.0",
        "requests>=2.28.1",
        "anthropic>=0.5.0",
        "openai>=0.27.0",
        "python-dotenv>=0.21.0",
    ],
    entry_points={
        "console_scripts": [
            "terminal-chat=main:main",
        ],
    },
)
