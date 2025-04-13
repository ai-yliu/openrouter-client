from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="openrouter-client",
    version="0.1.0",
    author="ai-yliu",
    author_email="",  # Update with your email
    description="A Python client for the OpenRouter API with text, PDF and image processing capabilities",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ai-yliu/openrouter-client",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.25.1",
        "PyPDF2>=2.0.0",
        "psycopg2-binary>=2.9", # Added for PostgreSQL logging
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "black>=21.0",
        ],
    },
    entry_points={
        'console_scripts': [
            'openrouter=openrouter_client:main',
            'compare-json=json_comparator:main',
            'compare-llms=compare_llms:main',
        ],
    },
)
