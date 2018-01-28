llvm-clang-dash-docsets
=======================

[LLVM](http://llvm.org/) 5.0.1 and [Clang](https://clang.llvm.org) 5.0.1 docsets
for dash. This script generates docsets for a subset of the html documentation
as well as separate docsets for the doxygen generate API documentation.

To generate the docsets simply execute:
``
    python llvm-clang-dash-docsets.py
``

Generating the doxygen based API docsets will take a while and the generated
docset archives are approx. 4.3GB in size.

__Requirements:__

  * [Sphinx](http://sphinx-doc.org/)
  * [Beautiful Soup](https://pypi.python.org/pypi/beautifulsoup4/4.3.2)
  * [Doxygen](https://www.stack.nl/~dimitri/doxygen/)
  * [zlib](https://zlib.net/)
