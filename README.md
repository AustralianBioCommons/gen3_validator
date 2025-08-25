# Gen3 Validator

**Gen3 Validator** is a Python toolkit designed to make working with Gen3 metadata schemas and data validation straightforward for developers.

With this tool, you can:

- **Resolve and flatten Gen3 JSON schemas** so you can work with them programmatically.
- **Validate JSON metadata files** against Gen3 schemas, catching schema violations early in your pipeline.
- **Check linkage integrity** between data nodes (e.g., ensuring all sample-to-subject references are valid).
- **Parse Excel-based metadata templates** and convert them to JSON for Gen3 ingestion.
- **Get detailed validation results and summary stats** as Python data structures or pandas DataFrames, making it easy to integrate with your own scripts or reporting tools.


## Docs
- [src docs](https://australianbiocommons.github.io/gen3_validator/)
- [example usage](https://github.com/AustralianBioCommons/gen3_validator/blob/main/docs/usage.md)

*Note: *I recommend you clone this repo, and walk through the examples in the [usage](https://github.com/AustralianBioCommons/gen3_validator/blob/main/docs/usage.md) page. The usage examples load data from the `tests/data` [directory](https://github.com/AustralianBioCommons/gen3_validator/tree/main/tests/data) so you can see how the data is structured.*


## Installation
```bash
pip install gen3_validator
pip show gen3_validator
```
---

## Dev Setup
1. Make sure you have [poetry](https://python-poetry.org/docs/#installing-with-pipx) installed.
2. Clone the repository.
3. Run the following command to activate the virtual environment.
```bash
eval $(poetry env activate)
```
4. Run the following command to install the dependencies.
```bash
poetry install
```
5. Run the following command to run the tests.
```bash
pytest -vv tests/
```
---

## License

See the [license](LICENSE) page for more information.
