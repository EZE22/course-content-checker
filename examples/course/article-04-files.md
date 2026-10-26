# Article 4: Files

In the previous article we wrote our own functions. Now we use them to read and write files on disk.

## Reading and Writing

The `open` function gives you a file object. Using it with a `with` block closes the file for you, even if something goes wrong.

Use the mode `"r"` to read and `"w"` to write. Writing with `"w"` replaces whatever was in the file before.

## Common Mistakes

| Mistake | Better habit |
| --- | --- |
| Forgetting to close a file | Use a `with` block |
| Writing with `"w"` when you meant to add | Use `"a"` to append |
| Assuming a file exists | Check the path or handle the error |

## Try It Yourself

1. Write a file called `notes.txt` with two lines of text.
2. Read it back and print each line.
3. Append a third line and read the file again.

## Why This Matters for an FDE

Most customer data arrives as files. Reading them safely is a daily task for a forward deployed engineer.

## Comprehension Check

1. What does a `with` block do for an open file?
2. What is the difference between the modes `"w"` and `"a"`?
