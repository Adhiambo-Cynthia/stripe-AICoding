"""Only one thing needs to change: parse_term gets a branch for (. 
A parenthesized group then counts as a single term."""
import re

# ------------------ TOKENIZER ----------------

TOKEN = re.compile(r"""
      (?P<SPACE>  \s+                    )   # skipped
    | (?P<STRING> "[^"]*"                )   # "Corner Store", "Fish (and) Chips"
    | (?P<NUMBER> -?\d+(?:\.\d+)?        )   # 200, -5, 99.5
    | (?P<OP>     =|!=|>=|<=|<|>        )   # two-char operators before one-char ones
    | (?P<PAREN>  [()]                   )   # ( and )
    | (?P<WORD>   [A-Za-z_][A-Za-z0-9_]* )   # field names and AND / OR
""", re.VERBOSE)
# ------------------ TOKENIZER ----------------

# ADD COMMENT: Turns a condition text into (KIND, Value) tuples. Examples of KINDs would be FIELD, STR(for String literal), NUM, OP(for operators).
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
# Turns condition tokens into a small tree. Node shapes:
#   ("AND", left_node, right_node), ("OR", left_node, right_node)
#   ("COMPARE", left_token, operator, right_token)
#   ("FLAG", field_name)                              -> a bare boolean field
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self): # Looks at the next token's kind without moving the cursor. Returns None at the end                              
        if self.pos < len(self.tokens):
            return self.tokens[self.pos][0]
        else:
            return None
        
    def advance(self): # return the next token and move the cursor
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    # Reads a chain of terms joined by AND/OR and combines them into one tree
    def parse_expression(self):
        node = self.parse_term() #read the first node

        while self.peek() in ("AND", "OR"):
            keyword = self.advance()[0] #the AND/OR itself
            node = (keyword, node, self.parse_term()) # so the other nodes are children of this node
        return node

    # Reads one condition: a comparison like amount > 1000, or a bare field like fraud_flag or a (group)
    # and returns it as a Node
    # term := "(" expression ")" | operand OP operand | FIELD
    def parse_term(self):
        if self.peek() == "(":                  # a parenthesized group counts as one term
            self.advance()                      # skip "("
            node = self.parse_expression()      # parse the inside; it stops at the matching ")"
            self.advance()                      # skip ")"
            return node # return that entire group as a single term

        left = self.advance()
        if self.peek() == "OP": 
            operator = self.advance()[1]
            return ("COMPARE", left, operator, self.advance())
        return ("FLAG", left[1])


# Accepts a rule and returns its action and condition tree
def parse_rule(rule): 
    """Accepts 'ACTION IF condition'""" 
    
    action, sep, condition_text = rule.strip().partition(" IF ")
    action = action.strip().upper()  # normalize for comparison

    return action, Parser(tokenize(condition_text)).parse_expression()

# MAIN function
# ------------------ EVALUATOR ----------------
# ADD COMMENT: Takes a list of transactions and rules and returns a list of decisions
#("ACCEPT"/"BLOCK"), one per transaction, in input order.
def evaluate(transactions, rules):
    # Step 1: Parse the rules once to extract the action and condition tree of each.
    parsed = [parse_rule(rule) for rule in rules] 

    results = []
    # Ietrate through the transactions and for each iterate the parsed rules
    for transaction in transactions:
        decision = "ACCEPT"
        for action, condition in parsed:
            if matches(condition, transaction):
                decision = action # the first match decides
                break                                   
        results.append(f"{decision}")
    
    return results

# Recursively Walks down condition tree against one transaction
def matches(node, txn) -> bool:
    kind = node[0]
    if kind == "AND":
        return matches(node[1], txn) and matches(node[2], txn)
    if kind == "OR":
        return matches(node[1], txn) or matches(node[2], txn)
    if kind == "FLAG":
        return txn.get(node[1]) is True               # only the real True; missing counts as False
    _, left, operator, right = node # A compare node
    return compare(operand_value(left, txn), operator, operand_value(right, txn))

def operand_value(token, txn: dict):
    kind, value = token
    if kind == "FIELD":
        return txn.get(value, MISSING)
    return value                     # STRING, BOOL or NUM literal

MISSING = object()

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

    # --------------- TESTS PART 3 -------------------
    # --- Example from the task ---
    corner_rule = ['BLOCK IF (country = "US" OR country = "CA") AND merchant = "Corner Store"']
    assert evaluate([{"country": "US", "merchant": "Corner Store"}], corner_rule) == ["BLOCK"]
    assert evaluate([{"country": "CA", "merchant": "Corner Store"}], corner_rule) == ["BLOCK"]
    assert evaluate([{"country": "FR", "merchant": "Corner Store"}], corner_rule) == ["ACCEPT"]
    assert evaluate([{"country": "US", "merchant": "Other"}], corner_rule) == ["ACCEPT"]

    # --- Parentheses override left-to-right for AND/OR ---
    tff = [{"a": True, "b": False, "c": False}]
    assert evaluate(tff, ['BLOCK IF a OR b AND c']) == ["ACCEPT"]       # (a OR b) AND c
    assert evaluate(tff, ['BLOCK IF a OR (b AND c)']) == ["BLOCK"]      # grouping changes the answer
    assert evaluate(tff, ['BLOCK IF (a OR b) AND c']) == ["ACCEPT"]     # same as no parentheses

    # --- Left-to-right continues after a group ---
    tfff = [{"a": True, "b": False, "c": False, "d": False}]
    assert evaluate(tfff, ['BLOCK IF a OR (b AND c) AND d']) == ["ACCEPT"]  # (a OR (b AND c)) AND d
    assert evaluate(tfff, ['BLOCK IF a OR ((b AND c) AND d)']) == ["BLOCK"]

    # --- Redundant and deep nesting, checked for every combination of values ---
    assert evaluate([{"a": True}], ['BLOCK IF ((a))']) == ["BLOCK"]
    assert evaluate([{"a": False}], ['BLOCK IF (((a)))']) == ["ACCEPT"]
    for a in (True, False):
        for b in (True, False):
            for c in (True, False):
                for d in (True, False):
                    txn = [{"a": a, "b": b, "c": c, "d": d}]
                    nested = a and (b or (c and d))
                    assert evaluate(txn, ['BLOCK IF (a AND (b OR (c AND d)))']) == ["BLOCK" if nested else "ACCEPT"]
                    two_groups = (a or b) and (c or d)
                    assert evaluate(txn, ['BLOCK IF (a OR b) AND (c OR d)']) == ["BLOCK" if two_groups else "ACCEPT"]

    # --- Parentheses inside quotes are literal text ---
    fish = [{"merchant": "Fish (and) Chips"}]
    assert evaluate(fish, ['BLOCK IF merchant = "Fish (and) Chips"']) == ["BLOCK"]
    assert evaluate(fish, ['BLOCK IF (merchant = "Fish (and) Chips")']) == ["BLOCK"]
    assert evaluate(fish, ['BLOCK IF merchant = "Fish and Chips"']) == ["ACCEPT"]
    assert evaluate([{"merchant": "A) OR (B"}], ['BLOCK IF (merchant = "A) OR (B")']) == ["BLOCK"]
    assert evaluate([{"merchant": "Open ("}], ['BLOCK IF merchant = "Open ("']) == ["BLOCK"]

    # --- Part 2 features inside groups ---
    us = [{"country": "US", "amount": 1500, "fraud_flag": True}]
    assert evaluate(us, ['BLOCK IF (fraud_flag and "US" = country) or amount < 10']) == ["BLOCK"]
    assert evaluate(us, ['BLOCK IF (missing_flag OR city = "Paris") AND fraud_flag']) == ["ACCEPT"]
    assert evaluate(us, ['BLOCK IF (city != "Paris") OR (country = "CA")']) == ["ACCEPT"]  # missing field
    assert evaluate(us, ['BLOCK IF (amount>1000)AND(fraud_flag)']) == ["BLOCK"]            # no spaces

    # --- First match still decides ---
    assert evaluate(us, ['ACCEPT IF (fraud_flag OR city = "Paris")', 'BLOCK IF fraud_flag']) == ["ACCEPT"]
    assert evaluate(us, ['ACCEPT IF (city = "Paris")', 'BLOCK IF (fraud_flag)']) == ["BLOCK"]

    # --- Backward compatibility: conditions without parentheses ---
    assert evaluate(us, ['BLOCK IF country = "US"']) == ["BLOCK"]
    assert evaluate(us, ['BLOCK IF "US" = country']) == ["BLOCK"]
    assert evaluate(us, ['BLOCK IF fraud_flag']) == ["BLOCK"]
    assert evaluate(us, ['BLOCK IF country = "CA" OR amount > 1000']) == ["BLOCK"]
    assert evaluate([{"merchant": "Bread and Butter"}], ['BLOCK IF merchant = "Bread and Butter"']) == ["BLOCK"]
    assert evaluate(us, []) == ["ACCEPT"]
    assert evaluate([], corner_rule) == []


    print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
        run_tests()