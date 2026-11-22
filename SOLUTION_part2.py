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
    # expression := term ((AND | OR) term)*
    # One loop for both keywords left -> right gives them equal precedence.
    # Example 'a OR b AND c' -> ("AND", ("OR", a, b), c)
    def parse_expression(self):
        node = self.parse_term() #read the first node

        while self.peek() in ("AND", "OR"):
            keyword = self.advance()[0] #the AND/OR itself
            node = (keyword, node, self.parse_term()) # so the other nodes are children of this node
        return node

    # Reads one condition term: a comparison like amount > 1000, or a bare field like fraud_flag
    # and returns it as a Node
    # term := operand OP operand | FIELD
    def parse_term(self):
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
        for action, condition_tree in parsed:
            if matches(condition_tree, transaction):
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
   # A compare node
    _, left, operator, right = node 
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

# BECUASE THERE IS NO NESTING WE COULD HAVE DONE WITHOUT THE PARSER AND 
# THE CODE WOULD LOOK LIKE THIS FROM PART 1. The only chnage is in matches func
# instead of reading the terms and storing them in a tree, we evaluate them as we readt them in a loop

# Evaluates the term starting at index i. Returns (True/False, index of the next token)
def read_term(tokens, i, txn):
    if i + 1 < len(tokens) and tokens[i + 1][0] == "OP":     # comparison: 3 tokens
        left, operator, right = tokens[i], tokens[i + 1][1], tokens[i + 2]
        return compare(operand_value(left, txn), operator, operand_value(right, txn)), i + 3

    return txn.get(tokens[i][1]) is True, i + 1              # bare boolean field: 1 token


# Combines terms strictly left to right
def matches(condition_tokens, txn) -> bool:
    result, i = read_term(condition_tokens, 0, txn)          # first term

    while i < len(condition_tokens):
        keyword = condition_tokens[i][0]                     # AND or OR
        value, i = read_term(condition_tokens, i + 1, txn)   # next term
        result = (result and value) if keyword == "AND" else (result or value)

    return result


#  ------------------ TESTS ----------------
def run_tests(): 

    # --------------- TESTS PART 2 -------------------
    # --- Bare boolean fields: only the actual True matches ---
    flag_rule = ['BLOCK IF fraud_flag']
    assert evaluate([{"fraud_flag": True}], flag_rule) == ["BLOCK"]
    assert evaluate([{"fraud_flag": False}], flag_rule) == ["ACCEPT"]
    assert evaluate([{}], flag_rule) == ["ACCEPT"]                      # missing counts as False
    assert evaluate([{"fraud_flag": "true"}], flag_rule) == ["ACCEPT"]  # string is not a boolean
    assert evaluate([{"fraud_flag": 1}], flag_rule) == ["ACCEPT"]       # 1 is not True here

    # --- AND / OR truth tables ---
    for a in (True, False):
        for b in (True, False):
            txn = [{"a": a, "b": b}]
            assert evaluate(txn, ['BLOCK IF a AND b']) == ["BLOCK" if a and b else "ACCEPT"]
            assert evaluate(txn, ['BLOCK IF a OR b']) == ["BLOCK" if a or b else "ACCEPT"]

    # --- Equal precedence, strictly left to right ---
    tff = [{"a": True, "b": False, "c": False}]
    assert evaluate(tff, ['BLOCK IF a OR b AND c']) == ["ACCEPT"]       # (a OR b) AND c
    assert evaluate(tff, ['BLOCK IF b AND c OR a']) == ["BLOCK"]        # (b AND c) OR a

    # --- Keywords are case-insensitive ---
    both = [{"a": True, "b": True}]
    assert evaluate(both, ['BLOCK IF a and b']) == ["BLOCK"]
    assert evaluate(both, ['BLOCK IF a And b']) == ["BLOCK"]
    assert evaluate(tff, ['BLOCK IF b oR a']) == ["BLOCK"]

    # --- Mixing comparisons and booleans, either operand order ---
    us = [{"country": "US", "amount": 1500, "fraud_flag": True}]
    assert evaluate(us, ['BLOCK IF fraud_flag AND country = "US"']) == ["BLOCK"]
    assert evaluate(us, ['BLOCK IF "US" = country AND amount > 1000']) == ["BLOCK"]
    assert evaluate(us, ['BLOCK IF country = "CA" OR amount < 1000']) == ["ACCEPT"]

    # --- Quoted strings stay one token ---
    shop = [{"merchant": "Bread and Butter"}, {"merchant": "Bread OR Butter"}]
    assert evaluate(shop, ['BLOCK IF merchant = "Bread and Butter"']) == ["BLOCK", "ACCEPT"]
    assert evaluate(shop, ['BLOCK IF merchant = "Bread OR Butter"']) == ["ACCEPT", "BLOCK"]

    # --- First match still decides with compound rules ---
    assert evaluate(us, ['ACCEPT IF fraud_flag AND amount > 1000', 'BLOCK IF fraud_flag']) == ["ACCEPT"]

    print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
        run_tests()