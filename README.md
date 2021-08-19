# QTI to Numbas

A tool to convert QTI packages to Numbas exams.

This is an ambitious goal! At the moment, it can convert the following kinds of packages:

* a bank of multiple choice questions exported from Blackboard in QTI 2.1 format.
* a Canvas quiz created using the old quiz engine, exported in QTI 1.2 format.

It could be expanded to support more of the QTI specification.

There is no real error handling: packages containing unsupported items will fail.

I (Christian Lawson-Perfect) don't have access to Blackboard, so if you have a QTI package that doesn't work, please send it to me and I'll try to work out how to support it.

## Installation

This is a Python 3 script which requires a couple of packages to be installed.

To install the packages, run:

```
pip install -r requirements.txt
```

## Usage

To convert a package called `question_bank.zip`, run:

```
python qti_to_numbas.py question_bank.zip -o question_bank.exam
```

A .exam file containing all of the questions in the question bank will be created in the current directory.
You can upload this file to the Numbas editor.
