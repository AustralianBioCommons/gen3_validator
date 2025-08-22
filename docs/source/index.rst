Gen3 Validator
==============

**Gen3 Validator** is a Python toolkit designed to make working with Gen3 metadata schemas and data validation straightforward for developers.

With this tool, you can:

- **Resolve and flatten Gen3 JSON schemas** so you can work with them programmatically.
- **Validate JSON metadata files** against Gen3 schemas, catching schema violations early in your pipeline.
- **Check linkage integrity** between data nodes (e.g., ensuring all sample-to-subject references are valid).
- **Parse Excel-based metadata templates** and convert them to JSON for Gen3 ingestion.
- **Get detailed validation results and summary stats** as Python data structures or pandas DataFrames, making it easy to integrate with your own scripts or reporting tools.

----------------------

Getting Started:
--------------

**Installation:**

.. code-block:: bash

   pip install gen3_validator

For more details, see the `README <https://github.com/AustralianBioCommons/gen3_validator/blob/main/README.md>`_.

**Usage:**

- Clone this repo and walk through the examples in the `usage <https://github.com/AustralianBioCommons/gen3_validator/blob/main/docs/usage.md>`_ page.
- The usage examples load data from the ``tests/data`` directory so you can see how the data is structured.

----------------------

API Reference
-------------

.. toctree::
   :maxdepth: 2
   :caption: Modules

   gen3_validator
   gen3_validator.parsers

- :doc:`gen3_validator` — Main package: dictionary handling, linkage, schema resolution, and validation.
- :doc:`gen3_validator.parsers` — Parsers for data and Excel files.

----------------------

License
-------

See the `license <https://github.com/AustralianBioCommons/gen3_validator/blob/main/LICENSE>`_ page for more information.
