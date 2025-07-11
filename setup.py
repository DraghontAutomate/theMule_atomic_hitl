import setuptools
import os

# Function to read the contents of the README file
def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        long_description = fh.read()
    return long_description

# Function to read requirements from requirements.txt
def read_requirements():
    with open("requirements.txt", "r", encoding="utf-8") as req_file:
        return [line.strip() for line in req_file if line.strip() and not line.startswith("#")]

# Package metadata
NAME = "themule-atomic-hitl"
VERSION = "0.1.0" # Initial version
DESCRIPTION = "A Human-in-the-Loop tool for close guidance and precise text-based data modification."
LONG_DESCRIPTION = read_readme()
AUTHOR = "The Mule" # Placeholder
AUTHOR_EMAIL = "author@example.com" # Placeholder
URL = "https://github.com/themule73/theMule_atomic_hitl" # Placeholder, replace if actual URL exists
REQUIRES_PYTHON = ">=3.6"

# Our main package (themule_atomic_hitl) is in 'src/'
# Our examples package (examples) is in './examples/' (root level)
PACKAGE_DIR = {
    '': 'src',  # For packages like 'themule_atomic_hitl', look in 'src/'
    'examples': 'examples',  # For the 'examples' package, look in 'examples/'
}

PACKAGES = setuptools.find_packages(where='src') + ['examples'] # Add 'examples' as a top-level package

# Get dependencies
INSTALL_REQUIRES = read_requirements()

setuptools.setup(
    name=NAME,
    version=VERSION,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    url=URL,
    package_dir=PACKAGE_DIR,
    packages=PACKAGES,
    python_requires=REQUIRES_PYTHON,
    install_requires=INSTALL_REQUIRES,
    include_package_data=True, # To include files specified in MANIFEST.in
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License", # Assuming MIT based on LICENSE file, adjust if different
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha", # Or 4 - Beta if more mature
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Text Processing :: General",
        "Framework :: PyQt",
    ],
    entry_points={
        "console_scripts": [
            "themule-hitl-example=examples.run_tool:main", # Assuming run_tool.py has a main() function
        ]
    },
)
