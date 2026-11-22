# TASK: Payment Transaction Rule Engine

Build a rule engine that decides whether each payment transaction is **accepted** or **blocked**.

---

## 1. Inputs and output

### Transactions
A list of records. Each record is a mapping of named attributes, e.g.

```python
{"id": "t1", "amount": 1500, "currency": "USD", "country": "US", "card_type": "prepaid", "fraud_flag": True}
```

Attribute names are illustrative. Do not hard-code them. Any field may appear or be missing.

### Rules
A list of rule strings. Each rule has the format:

```
ACTION if CONDITION
```

- `ACTION` is `ACCEPT` or `BLOCK`
- `CONDITION` is text over the transaction's attributes (e.g. `amount > 1000`, `fraud_flag`)

Examples:

```python
rules = [
    "BLOCK if fraud_flag",
    'BLOCK if country == "US" AND amount > 1000',
    'ACCEPT if merchant == "Corner Store"',
]
```

> To parse a rule, split on the **first** ` if `. The action always comes first, so an `if` inside a quoted literal later in the condition (e.g. `merchant == "What if Cafe"`) is not affected.

### Output
A list of strings, one per transaction, **in input order**, each formatted as `"<transaction id>: <DECISION>"`:

```python
["t1: BLOCK", "t2: ACCEPT"]
```

---

## 2. Global semantics (apply to every part)

### Combination policy
- Rules are checked **in list order**. The **first matching rule decides**.
- If **no rule matches**, the transaction is **ACCEPTED**.

### Comparisons
A comparison is `field OP literal`, where:
- `OP` is one of `==`, `!=`, `>`, `>=`, `<`, `<=`
- `literal` is a **number** (integer or decimal) or a **double-quoted string**

**Equality is written `==` (two equals signs).** A single `=` is not an operator. `country == "US"` is valid; `country = "US"` is not.

### Type and missing-field rules
A comparison is **false for every operator, `!=` included**, when:
- the field is **missing** from the transaction, or
- the field value and the literal have **incompatible types**

Compatibility:
| Field value          | Compares with   |
|----------------------|-----------------|
| int / float          | numbers only    |
| str                  | strings only    |
| bool, None, other    | nothing (comparisons with them are always false) |

> Watch out for Python: `bool` is a subclass of `int`. Rule out `bool` explicitly before you check for a number, so a `True` field never matches `amount == 1`.

Examples:
- `{}` does **not** match `country != "US"` (missing field)
- `{"country": "US"}` does **not** match `country != 5` (string vs number)

> If the interviewer would rather raise an error than return false, the change should sit in **one method**, the type-compatibility check.

### Amounts
Amounts are **integers in the smallest currency unit** (e.g. cents). Comparisons are exact, so you never need float tolerance for amounts.

---

## 3. Parts

Each part extends what a condition can express. **Every earlier part must keep working.**

### Part 1: String equality and rule order

Support:
- A condition that compares **one field** with **one string constant** for **equality** (`==`).
- The field and the literal can sit on **either side** of `==`:
  - `country == "US"`
  - `"US" == country`
- Both outcomes (`ACCEPT` / `BLOCK`), first-match order, and default accept.

**Tests to write:**
- [ ] `BLOCK if country == "US"` splits into action `BLOCK` and condition `country == "US"`
- [ ] Default accept when no rule matches
- [ ] First match wins when two rules both match with different actions
- [ ] `country == "US"` and `"US" == country` behave the same
- [ ] Missing field leads to no match
- [ ] Non-string field value (e.g. `country: 5`) leads to no match
- [ ] Output order matches input order

---

### Part 2: Boolean fields with AND / OR

Keep all Part 1 behavior. Add:

1. **Boolean field conditions**: a boolean appears in a condition as a **bare field name**, e.g. `BLOCK if fraud_flag`.
   - The condition is true **only** when the transaction's value is the actual Python boolean `True`.
   - A **missing field counts as `False`**.
   - `False`, and any non-boolean value (the string `"true"`, the number `1`), also evaluate to false.
   - This is the only boolean form. There are no `true` / `false` literals, so `fraud_flag == true` is not supported.
2. **`AND` / `OR`** combining conditions.
   - The keywords are **case-insensitive**: `AND`, `and` and `And` are all the same. (Inside a quoted string they stay literal text.)
   - `AND` and `OR` have **equal precedence**.
   - They are evaluated **strictly left to right**.
   - So `a OR b AND c` means `(a OR b) AND c`, **not** `a OR (b AND c)`.

**Tokenizer requirement:**
- A quoted string is **one token**, even when it contains spaces or the words `AND` / `OR`.
- `merchant == "Bread and Butter"` gives the tokens `merchant`, `==`, `"Bread and Butter"`.

**Tests to write:**
- [ ] `fraud_flag` with value `True` matches
- [ ] `fraud_flag` with value `False` does not match
- [ ] `fraud_flag` missing does not match (counts as `False`)
- [ ] `fraud_flag` with value `"true"` or `1` does not match
- [ ] Simple `AND`, simple `OR`
- [ ] Mixing booleans and comparisons: `fraud_flag AND country == "US"`
- [ ] Lowercase / mixed-case keywords: `a and b`, `a Or b`
- [ ] Left-to-right: `a OR b AND c` where `a=T, b=F, c=F` gives **false** (standard precedence would give true)
- [ ] Quoted literal containing spaces: `"Bread and Butter"`
- [ ] Quoted literal containing `AND` / `OR` keywords
- [ ] All Part 1 tests still pass

---

### Part 3: Parentheses and nested combinations

Keep all Part 2 behavior. Add:

- **Arbitrary nesting** of parentheses, equality tests, boolean fields, and `AND` / `OR`.
  - e.g. `(country == "US" OR country == "CA") AND merchant == "Corner Store"`
- **Precedence**: `AND` / `OR` keep equal precedence and left-to-right evaluation, **except** that parentheses explicitly control grouping.
  - `a OR (b AND c)` evaluates `(b AND c)` first.
- **Quoted literals**: parentheses inside a quoted string are literal characters, not grouping symbols.
  - `merchant == "Fish (and) Chips"` is a single comparison.

**Tests to write:**
- [ ] `(country == "US" OR country == "CA") AND merchant == "Corner Store"`
- [ ] `a OR (b AND c)` with `a=T, b=F, c=F` gives **true** (compare with the Part 2 case without parentheses)
- [ ] Deep nesting: `((a))`, `(a AND (b OR (c AND d)))`
- [ ] `"Fish (and) Chips"` parsed as one literal
- [ ] All Part 1 and Part 2 tests still pass

---

## 4. Suggested design

Keep it small, with clear seams. Don't over-engineer.

```
condition text ──► tokenize ──► parse (AST) ──► evaluate(ast, txn) ──► bool
```

| Component        | Responsibility |
|------------------|----------------|
| `tokenize(text)` | Produce tokens: quoted strings (kept whole), numbers, identifiers, `AND`/`OR`, operators, `(`, `)`. Match two-character operators (`==`, `!=`, `>=`, `<=`) before one-character ones (`>`, `<`). |
| `parse_rule(rule)` | Split `ACTION if CONDITION` on the first ` if ` into `(action, condition)` |
| `parse(tokens)`  | Build an AST. Grammar below. |
| `compare(value, op, literal)` | **The single method** that owns the type and missing-field rules |
| `evaluate(node, txn)` | Walk the AST. A bare field is `txn.get(field) is True`. |
| `decide(txns, rules)` | Parse each rule **once**, then apply first-match order with default accept |

### Grammar (Part 3; Parts 1–2 are subsets)

```
expr       := term ( ("AND" | "OR") term )*      # equal precedence, left-assoc, case-insensitive
term       := "(" expr ")" | comparison | IDENT  # IDENT alone = boolean field, true only if value is True
comparison := operand OP operand                 # exactly one side is IDENT, the other a literal (never field vs field)
operand    := IDENT | NUMBER | STRING
OP         := "==" | "!=" | ">" | ">=" | "<" | "<="
```

> When the literal is on the left (`"US" == country`), **flip** asymmetric operators: `5 < amount` becomes `amount > 5`.

---

## 5. Assumptions

1. Each rule is a string in the format `ACTION if CONDITION`, where the action is `ACCEPT` or `BLOCK`.
2. Equality is `==`. A single `=` is not an operator.
3. Boolean fields hold Python `True` / `False`. The only boolean form is a bare field name (e.g. `BLOCK if fraud_flag`), true only when the value is `True`. A missing field counts as `False`. There are no `true` / `false` literals.
4. `AND` / `OR` are case-insensitive.
5. **All rules are well-formed.** No validation or error handling for malformed rules (bad syntax, unbalanced parentheses, unknown operators).
6. A comparison is always **one field against one literal value**. Field-vs-field (`a == b`) and literal-vs-literal are out of scope.
7. Output is a list of `"<transaction id>: <DECISION>"` strings in input order.
