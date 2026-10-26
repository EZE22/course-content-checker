# Article 2: Loops

In the previous article we learned how variables store values. Now we use loops to repeat work without copying code.

## The for Loop

A `for` loop goes through the items in a list one at a time. For example, `for name in names:` runs the loop body once for each name.

When you only need a count, use `range`. The call `range(3)` gives you 0, 1, and 2.

## Common Mistakes

The table below lists mistakes that beginners often make with loops.

| Mistake | Better habit |
| --- | --- |
| Forgetting the colon after the loop line | End the line with a colon |
| Changing a list while looping over it | Build a new list instead |
| Expecting `range(3)` to include 3 | Remember it stops before 3 |

## Try It Yourself

1. Make a list of three fruits.
2. Write a `for` loop that prints each fruit.
3. Change the loop so it prints the position of each fruit using `enumerate`.

## Why This Matters for an FDE

Loops are how scripts handle many records at once. A field engineer who can loop safely can clean a whole spreadsheet in minutes.

## Comprehension Check

1. How many times does `for i in range(5):` run its body?
2. Why is it risky to change a list while looping over it?
