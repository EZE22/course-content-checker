# Article 7: Testing

In the previous article we split code into modules. Now we write small tests so we can trust that code.

## Your First Test

A test is a function that checks one thing. With pytest, the function name starts with `test_` and uses `assert` to state what should be true.

For example, `assert double(4) == 8` fails loudly if `double` is broken.

## Common Mistakes

| Mistake | Better habit |
| --- | --- |
| Testing many things in one function | Write one small test per idea |
| Skipping the edge cases | Try empty input and zero |
| Never running the tests | Run them after every change |

## Try It Yourself

1. Create a file called `test_math_tools.py`.
2. Write a test that checks `double(4)` equals 8.
3. Run `pytest` and read the result.

## Comprehension Check

1. What word starts the name of every pytest test function?
2. Why is one small test per idea easier to fix?
