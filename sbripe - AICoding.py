# Transaction Rule Engine
"""
Transaction Rule Engine
You are given a list of transactions (dicts of string fields) and a list of rule strings. 
Each rule is 'ACTION if CONDITION', where ACTION is ACCEPT or BLOCK. 
Rules are checked in order; the first rule whose condition is true decides the outcome. If no rule matches, the outcome is ACCEPT. 
Output one line per transaction: transaction-id:DECISION.

PART 1
Conditions are a single boolean field name, e.g. BLOCK if fraud_flag. A field is true only if its value is the string "true". A missing field counts as false.

WHAT TO SHOW:
- Simple design with clear seams. 
- You reject the AI’s over-engineering/ correct it yourself. 
- Tests for the default, a missing field, and first-match-wins.
"""

#  ----------------------- PART 1 ----------------------------
# HELPER
def parse_rule(rule):
    # split on the first " if " into action and condition
    action, sep, condition = rule.strip().partition(" if ")  # sep is "" when " if " is missing
    action = action.strip().upper()  # normalize only for comparison

    # reject malformed rules
    if not sep or action not in ("ACCEPT", "BLOCK") or not condition.strip():  # missing piece
        return None
    return action, condition.strip()  # (action, condition text)

# HELPER
def evaluate(condition, txn):
    transaction_value = txn.get(condition, "").strip().lower()
    return transaction_value == "true"  # only "true" counts; missing -> ""

# MAIN
def process_transactions(transactions, rules):
    # step 1: parse every rule once, dropping malformed ones
    parsed = [p for p in (parse_rule(r) for r in rules) if p]  # keeps insertion order

    # Step 2: convert transactions using csv.DictReader to ensure consistent field access and stripping whitespace if needed. 
    # reader = csv.DictReader(StringIO(csv_string.strip()))
    # This is optional if transactions are already dicts with clean data.

    # step 2: Iterate through each transaction, evaluate the rules and apply the decision of first matching rule
    output = []  
    for txn in transactions:  
        decision = "ACCEPT"  # default descision
        
        for rule in parsed: 
            action, cond = rule
            if evaluate(cond, txn):  # condition holds
                decision = action  # take this rule's action
                break  # later rules are not evaluated
        output.append(f"{txn.get('id')}:{decision}")  
    
    return output 

#  ----------------------- PART 2 ----------------------------
"""
- Part 2: Add comparisons (=, !=, >, <, >=, <=) and AND/OR. 
- The field or the literal may appear on either side, e.g. "US" = country. String literals use double quotes. 
- AND/OR have no precedence; evaluate left to right.

What Changes in the Approach:

"""

import re

# HELPER: Split conditions while preserving quoted strings
def tokenize(condition):
    return re.findall(
        r'"[^"]*"|>=|<=|!=|==|>|<|[A-Za-z_]\w*|-?\d+(?:\.\d+)?',
        condition
    )
# The regex evaluates the following choices in order (separated by the | operator). . 
# It processes the string sequentially from left to right, matching the first rule that applies from its list of choices.
# 1. Quoted strings: "[^"]*" matches any sequence of characters enclosed in double quotes e.g., "active", "John"
# 2. Comparison operators: >=, <=, !=, =, >, < match the respective comparison operators.
# 3. Ordinary words: [A-Za-z_]\w* matches field names and AND/OR connectors
# 4. Numbers: -?\d+(?:\.\d+)? matches numbers (integer or float)

# Example conditions BLOCK IF country = "RU" AND amount > 1000

# HELPER
def parse_rule(rule):
    # split on the first " if " into action and condition
    action, sep, condition = rule.strip().partition(" if ")  # sep is "" when " if " is missing
    action = action.strip().upper()  # normalize only for comparison

    # reject malformed rules
    if not sep or action not in ("ACCEPT", "BLOCK") or not condition.strip():  # missing piece
        return None
    return action, tokenize(condition.strip())  # (action, condition tokens)

# MAIN
def process_transactions(transactions, rules):
    parsed = [p for p in (parse_rule(r) for r in rules) if p]  # we want to parse the rules once and keep only the valid ones. 
    # This is more efficient than parsing them for every transaction.

    results = []

    # MAIN: Apply rules in order
    for transaction in transactions:
        decision = "ACCEPT"

        for rule in parsed:
            action, condition = rule
            if evaluate(condition, transaction): # build a more complex evaluate function to handle comparisons and AND/OR
                decision = action
                break

        results.append(f"{transaction.get('id')}:{decision}")

    return "\n".join(results)


# HELPER: Evaluate a condition left to right
def evaluate(condition_tokens, transaction):
    i = 0

    def evaluate_atom():
        nonlocal i # it reassigns i, which belongs to the outer function.

        left = condition_tokens[i]
        i += 1

        # A comparison: field - operator - value
        if i < len(condition_tokens) and condition_tokens[i] in (
            "=", "!=", ">", "<", ">=", "<="
        ):
            op = condition_tokens[i]
            i += 1
            right = condition_tokens[i]
            i += 1

            return compare(
                get_value_from_transaction(left, transaction), # get that fields value in the transaction itself
                op,
                get_value_from_transaction(right, transaction)
            )

        # A standalone boolean field
        return transaction.get(left,"").strip().lower() == "true"

    result = evaluate_atom() # the first atom/unit before an operator AND/OR in the condition is evaluated, and then we will process the rest of the tokens in a loop

    while i < len(condition_tokens):
        logical_op = condition_tokens[i]
        i += 1

        next_result = evaluate_atom()

        # handles the logical operators AND/ OR, left to right, without precedence. 
        if logical_op.upper() == "AND":
            result = result and next_result
        elif logical_op.upper() == "OR":
            result = result or next_result

    return result


def to_num(x):
    try: return float(x)  # numeric view for comparisons
    except (TypeError, ValueError): return None  # not a number

# HELPER: Resolve a field name or string literal
def get_value_from_transaction(token, transaction):
    # 1: if token is a value ie string literal or number, return the value itself
    if token.startswith('"') and token.endswith('"'): # strip quotes for string literals and returns the string
        return token[1:-1]
    
    if to_num(token) is not None: # check if the token is a number (integer or float) and return it as is
        return token

    # 2: If token is a field, return the field value
    return transaction.get(token)

# HELPER: Evaluate one comparison
def compare(left, op, right):
    if left is None or right is None:
        return False

    ln, rn = to_num(left), to_num(right)  # numeric views of both sides
    if ln is not None and rn is not None:  # both numeric -> compare as numbers for every op
        left, right = ln, rn
    elif op in (">", "<", ">=", "<="):  # ordering needs two numbers, so if either side is not a number, return False
        return False

    if op == "=":
        return left == right
    if op == "!=":
        return left != right
    if op == ">":
        return left > right
    if op == "<":
        return left < right
    if op == ">=":
        return left >= right
    if op == "<=":
        return left <= right

    return False

#  ----------------------- PART 3 ----------------------------

"""
For part 3 of this problem. We would like to support parenthesis. 
- This includes examples like "US" = country AND (amount >= 10000 OR fraud_flag) blocks when amount is exactly 10000 and fraud is false, 
- Nested groups, a AND ((b OR c) AND (c)), evaluate correctly, A literal containing parentheses ("Fish (and) Chips") stays one token, 
- A transaction missing the field used inside the parentheses doesn’t crash and falls through to the default

We only need to update the tokenizer and evaluate function to support nested parentheses.
The key change is using a recursive-descent parser: when it encounters (, it evaluates the grouped expression recursively until it reaches the matching )
"""
# HELPER: Tokenize conditions, preserving quoted strings
def tokenize(condition):
    return re.findall(
        r'"[^"]*"|>=|<=|!=|=|>|<|\(|\)|[A-Za-z_]\w*|-?\d+(?:\.\d+)?',  # add a parenthesis group after the operator group: |(\(|\))|
        condition
    )


# HELPER: Evaluate conditions with nested parentheses
def evaluate(condition_tokens, transaction):
    i = 0

    # HELPER: Evaluate an atom or parenthesized expression
    def evaluate_atom():
        nonlocal i

        if condition_tokens[i] == "(":
            i += 1
            result = evaluate_expression()
            i += 1  # Skip closing parenthesis
            return result

        left = condition_tokens[i]
        i += 1

        # Comparison: operand operator operand
        if i < len(condition_tokens) and condition_tokens[i] in (
            "=", "!=", ">", "<", ">=", "<="
        ):
            op = condition_tokens[i]
            i += 1

            right = condition_tokens[i]
            i += 1

            return compare(
                get_value(left, transaction),
                op,
                get_value(right, transaction)
            )

        # Standalone boolean field
        return transaction.get(left, "").strip().lower() == "true"

    # HELPER: Evaluate AND/OR left to right
    def evaluate_expression():
        nonlocal i

        result = evaluate_atom()

        while i < len(condition_tokens) and condition_tokens[i] != ")":
            logical_op = condition_tokens[i].upper()
            i += 1

            next_result = evaluate_atom()

            if logical_op == "AND":
                result = result and next_result
            else:  # OR
                result = result or next_result

        return result

    return evaluate_expression()

