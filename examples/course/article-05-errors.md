# Article 5: Errors

In the previous article we read and wrote files, which can fail in many ways. Now we learn to handle errors calmly.

## Try and Except

Wrap risky code in a `try` block and describe the response in an `except` block. If no error happens, the `except` block is skipped.

Name the error you expect, such as `FileNotFoundError`. That way other problems still show up.

## Common Mistakes

The table below lists mistakes that beginners often make with errors.

| Mistake | Better habit |
| --- | --- |
| Catching everything with a bare `except` | Catch the specific error |
| Ignoring the error silently | Print or log a useful message |
| Putting too much code inside `try` | Keep the block small | Easier to debug |

## Try It Yourself

1. Write code that opens a file that does not exist.
2. Catch the `FileNotFoundError` and print a friendly message.
3. Add an `else` block that prints the file size when no error happens.

## Why This Matters for an FDE

Customer data is rarely perfect. A script that fails with a clear message saves everyone time.

## Comprehension Check

1. Why is a bare `except` risky?
2. When does the `else` block of a `try` statement run?
