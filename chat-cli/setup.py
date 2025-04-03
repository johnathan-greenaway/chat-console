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
    name="chat-console",
    version=version,
    author="Johnathan Greenaway",
    author_email="john@fimbriata.dev",
    description="A command-line interface for chatting with LLMs, storing chats and (future) rag interactions",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/wazacraftrfid/chat-console",
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
            "chat-console=app.main:main",
            "c-c=app.main:main",  
        ],
    },
)
