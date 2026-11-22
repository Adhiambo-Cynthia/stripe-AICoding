"""
Design
Three layers, each testable on its own:

    1.Tokenizer : turns the condition string into tokens and is the only code that looks at characters. Quoted text becomes one string token, so words inside it can never become operators.
    2.Parser : turns condition tokens into a small tree that encodes precedence and nesting.
    3.Evaluator : walks the tree against one transaction.
"""
import re

# ------------------ TOKENIZER ----------------
# The only code that looks at characters. Turns a condition into (KIND, VALUE) tuples:
#   'country == "US" AND fraud_flag'
#   -> [("FIELD", "country"), ("OP", "=="), ("STR", "US"), ("AND", "AND"), ("FIELD", "fraud_flag")]
# Kinds: FIELD, STR, NUM, OP, AND, OR, "(", ")"

# Alternatives are tried left to right at each position, so order matters:
# STRING first, so anything inside quotes is never read as an operator, keyword or paren.
TOKEN = re.compile(r"""
      (?P<SPACE>  \s+                    )   # skipped
    | (?P<STRING> "[^"]*"                )   # "Corner Store", "Fish (and) Chips"
    | (?P<NUMBER> -?\d+(?:\.\d+)?        )   # 200, -5, 99.5
    | (?P<OP>     =|!=|>=|<=|<|>        )   # two-char operators before one-char ones
    | (?P<PAREN>  [()]                   )   # ( and )
    | (?P<WORD>   [A-Za-z_][A-Za-z0-9_]* )   # field names and AND / OR
""", re.VERBOSE)
# ------------------ TOKENIZER ----------------

# ADD COMMENT: Turns a condition text into (KIND, Value) tuples. 
# Examples of KINDs would be FIELD, STR(for String literal), NUM, OP(for operators).
def tokenize(text):
    
    tokens = []
    pos = 0
    while pos < len(text):
        match = TOKEN.match(text, pos)
        if match is None:
            raise ValueError(f"unexpected character {text[pos]!r} at position {pos}")
        kind, piece = match.lastgroup, match.group()
        pos = match.end()

        if kind == "STRING":
            tokens.append(("STR", piece[1:-1]))                           # drop the quotes
        elif kind == "NUMBER":
            tokens.append(("NUM", float(piece) if "." in piece else int(piece)))
        elif kind == "OP":
            tokens.append(("OP", piece))
        elif kind == "PAREN":
            tokens.append((piece, piece))
        elif kind == "WORD":
            if piece.upper() in ("AND", "OR"):                            # keywords are case-insensitive
                tokens.append((piece.upper(), piece.upper()))
            else:
                tokens.append(("FIELD", piece))
        # SPACE: nothing to add

    return tokens

# ------------------ PARSER ----------------
# ADD COMMENT: Accepts a rule and return the actions and tokenized condition
def parse_rule(rule): 
    """Accepts 'ACTION IF condition'""" 
    
    action, sep, condition_text = rule.strip().partition(" IF ")
    action = action.strip().upper()  # normalize for comparison

    return action, tokenize(condition_text)
        #parser = Parser(tokenize(condition_text)) 

# MAIN function
# ------------------ EVALUATOR ----------------
# ADD COMMENT: Takes a list of transactions and rules and returns a list of decisions
#("ACCEPT"/"BLOCK"), one per transaction, in input order.
def evaluate(transactions, rules):
    # Step 1: Parse the rules once to extract the action and tokenized condition of each.
    parsed = [parse_rule(rule) for rule in rules] 

    results = []
    # Ietrate through the transactions and for each iterate the parsed rules
    for transaction in transactions:
        decision = "ACCEPT"
        for action, condition_tokens in parsed:
            if matches(condition_tokens, transaction):
                decision = action # the first match decides
                break                                   
        results.append(f"{decision}")
    
    return results

# Evaluates a transaction against a rule conditions
def matches(condition_tokens , txn) -> bool:       # Part 1: exactly one comparison -> will rename this evaluate
    left, operator, right = condition_tokens
    operator = operator[1]
    return compare(operand_value(left, txn), operator, operand_value(right, txn))

def operand_value(token, txn: dict):
    kind, value = token
    if kind == "FIELD":
        return txn.get(value, MISSING)
    return value                     # STRING, BOOL or NUM literal

MISSING = object()
# USE THIS IF WE ARE ONLY DOING EQUALITY CHECKS, NOT COMPARISONS
# def equal(a, b) -> bool:
#     return a is not MISSING and b is not MISSING and type(a) is type(b) and a == b
def to_num(x):
    try: return float(x)  # numeric view for comparisons
    except (TypeError, ValueError): return None  # not a number

def compare(left, op, right):
    if left is MISSING or right is MISSING:
        return False

    leftnum, rightnum = to_num(left), to_num(right)  # numeric views of both sides
    if leftnum is not None and rightnum is not None:  # both numeric -> compare as numbers for every op
        left, right = leftnum, rightnum
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


#  ------------------ TESTS ----------------
def run_tests(): 
# Part 1: one condition, six operators --- 
    txns = [{"country": "RU", "merchant": "acme", "amount": 50}, 
            {"country": "US", "merchant": "stripe", "amount": 5000}, # satisfies 2 rules but only the first one will be  used
            {"country": "US", "merchant": "acme", "amount": 150}, # checks operators
            {"country": "US", "merchant": "acme", "amount": 900}, ] 

    rules = ['BLOCK IF country = "RU"', 'ACCEPT IF merchant = "stripe"', 
            'ACCEPT IF amount < 200', 'BLOCK IF amount >= 500'] 

    assert evaluate(txns, rules) == ["BLOCK", "ACCEPT", "ACCEPT", "BLOCK"]

    t = [{"country": "US", "amount": 200}]
    assert evaluate(t, ['BLOCK IF amount != 200']) == ["ACCEPT"]
    assert evaluate(t, ['BLOCK IF amount <= 200']) == ["BLOCK"]
    assert evaluate(t, ['BLOCK IF amount > 200']) == ["ACCEPT"]
    assert evaluate(t, ['BLOCK IF amount > 199.5']) == ["BLOCK"]
    assert evaluate(t, ['BLOCK IF country != "FR"']) == ["BLOCK"]

    # --- Decisions on edge cases ---
    assert evaluate(t, []) == ["ACCEPT"]                                # no rules
    assert evaluate([], rules) == []                                  # no transactions
    assert evaluate(t, ['BLOCK IF city = "Paris"']) == ["ACCEPT"]       # missing field
    assert evaluate(t, ['BLOCK IF city != "Paris"']) == ["ACCEPT"]      # missing field
    assert evaluate([{"amount": "500"}], ['BLOCK IF amount > 200']) == ["BLOCK"]  # numeric string
    assert evaluate(t, ['BLOCK IF country > 5']) == ["ACCEPT"]          # type mismatch
    assert evaluate(t, ['ACCEPT IF amount = 200', 'BLOCK IF amount = 200']) == ["ACCEPT"]

    print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
        run_tests()


