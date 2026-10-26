# Article 3: Functions

In the previous article we used loops to repeat work. Functions let us give a block of work a name and reuse it.

## Defining a Function

A function starts with the word `def`, a name, and parentheses. The indented lines below it are the body.

Use `return` to send a value back to the caller. Without it, the function gives back `None`.

## Common Mistakes

The table below lists mistakes that beginners often make with functions.

| Mistake | Better habit |
| --- | --- |
| Printing a result instead of returning it | Use `return` so the caller can reuse it |
| Forgetting to call the function | Add parentheses, as in `greet()` |
| Using a list as a default value | Use `None` and build the list inside |

## Try It Yourself

1. Write a function called `double` that returns its input times two.
2. Call it with the number 4 and print the result.
3. Add a second function that greets a person by name.

## Why This Matters for an FDE

Small, named functions make a script easier to test and easier to hand over to a customer team.
