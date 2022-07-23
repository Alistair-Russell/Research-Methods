# BUS 989 COURSE NAME

[[_TOC_]]

## Introduction

BUS989 trading assignments make use of common python libraries (e.g. numpy, pandas) as well as the ib_insync library for trading through Interactive Brokers (IBKR) with a paper trading account. Do not use a live IBKR account for this... I

## Getting started

### START HERE
Ensure you have the following:
- python3 installed on your machine
- A free IBKR **paper trading** account
- An installation of either IB Trader Workstation or IB Gateway
- Anaconda-Navigator installation in order to launch Jupyter Lab

There are several tutorials included in this repository that provide some guidance for approaching the course. A general guide would be the following:

**At the start of the course, before any assignments:**
1. REVIEW Jupyter notebooks operations so that you can quickly build and test code. (TODO: JUPYTER TUTORIAL)
2. REVIEW the basic python slides from BUS721 (TODO: PYTHON TUTORIAL), and watch this short video on [list comprehension](https://www.youtube.com/watch?v=E1ZAVEmRwyI) here is a rough breakdown of what you should learn/know [Python Knowledge List](#python-knowledge-list)
3. REVIEW common numpy/pandas operations. (TODO: DATA ANALYSIS TUTORIAL) You do **not** need to memorize every function/method, you just need a general idea of the common use cases so that you have a rough idea of what kind of computations a dataframe does well. This will help you avoid "reinventing the wheel" in the assignments.
4. SKIM the ib_insync [tutorials](./tutorials) included in this repository. These show common interactions with IBKR. Again, don't memorize, just read through to get the gist of it.

**For each trading assignment**
1. UNDERSTAND the textbook chapters and paper of the week.
2. PLAN your approach using comments and docstrings (TODO: PROBLEM SOLVING TUTORIAL)
3. BUILD your solution (and iterate)

### Environmment Setup
TODO: add environment setup review

### Python Knowledge List

I won't waste your time, here are the essentials...
>>>
Know already
- Variables
- Conditions
- Chained Conditionals
- Operators
- Control Flow (if/elif/else)
- Loops and iterables
- Functions
- Common Python Methods (built-in library)
- Jupyter Notebooks
- Numpy
- Pandas

Learn now
- List Comprehension (saves a LOT of your time and effort, very easy to read)
- Classes and Object Oriented Programming (not covered in bus721, great for portfolio rebalancing)
- More numpy
- More pandas

If you feel ambitious
- Iterators and Generators (generators are used for retrieving stock data in ib_insync)
- Async IO (ib_insync uses this behind the scenes, understanding asynchronous programming is generally useful)
- Lambda Functions (these are cool)
>>>

### Jupyter
TODO: add jupyter tips and tricks

## Assignments
TODO: add assignments

## Authors and acknowledgment
Alistair Russell (apr4@sfu.ca)
Christina Atanasova

