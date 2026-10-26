# Article 6: Modules

In the previous article we handled errors. Now we split code across files and reuse code that other people wrote.

## Importing Code

A module is a Python file you can load with `import`. For example, `import math` gives you tools such as `math.sqrt`. You can also pull in one name with `from math import sqrt` and call `sqrt(16)` directly.

## Common Mistakes

The table below lists mistakes that beginners often make with modules.

| Mistake | Better habit |
| --- | --- |
| Naming your file `math.py` | Pick a name that is not in the standard library |
| Importing everything with a star | Import only the names you need |
| Putting imports in the middle of a file | Keep imports at the top |

## Try It Yourself

1. Import the `random` module and print a random number between 1 and 10.
2. Import only the `sqrt` function from `math` and print the square root of 49.

#### Tip

If an import fails, check that the file name and the spelling match exactly.

## Why This Matters for an FDE

Real projects are built from many modules. Knowing how to import cleanly keeps a customer project tidy.

## Comprehension Check

1. What is the difference between `import math` and `from math import sqrt`?
2. Why should you avoid naming your own file `math.py`?
