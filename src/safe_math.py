"""
safe_math.py — Safe mathematical expression parser.

Replaces eval() for user-defined equations by walking the AST and only
allowing a restricted set of operations (arithmetic, comparisons, numpy
math functions, variables, and numeric literals).

Usage:
    func = safe_make_function("A1*np.exp(-b1*x) + c", ["A1", "b1", "c"])
    result = func(x_array, 1.0, 0.5, 2.0)
"""

import ast
import operator
import numpy as np


# Whitelisted numpy functions (safe, pure-math)
_SAFE_NP_FUNCS = {
    "exp", "log", "log2", "log10", "sqrt", "abs",
    "sin", "cos", "tan", "arcsin", "arccos", "arctan", "arctan2",
    "sinh", "cosh", "tanh", "arcsinh", "arccosh", "arctanh",
    "power", "square", "cbrt", "ceil", "floor", "round",
    "sign", "clip", "maximum", "minimum",
    "pi", "e", "inf",
}

# Allowed binary operators
_SAFE_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# Allowed unary operators
_SAFE_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Allowed comparison operators
_SAFE_CMPOPS = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


class _SafeEvaluator(ast.NodeVisitor):
    """Walk an AST tree and evaluate it safely."""

    def __init__(self, variables: dict):
        self.variables = variables

    def visit_Expression(self, node):
        return self.visit(node.body)

    def visit_Constant(self, node):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value).__name__}")

    def visit_Num(self, node):  # Python 3.7 compat
        return node.n

    def visit_Name(self, node):
        if node.id in self.variables:
            return self.variables[node.id]
        raise ValueError(f"Unknown variable: '{node.id}'")

    def visit_BinOp(self, node):
        op_type = type(node.op)
        if op_type not in _SAFE_BINOPS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = self.visit(node.left)
        right = self.visit(node.right)
        return _SAFE_BINOPS[op_type](left, right)

    def visit_UnaryOp(self, node):
        op_type = type(node.op)
        if op_type not in _SAFE_UNARYOPS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        return _SAFE_UNARYOPS[op_type](self.visit(node.operand))

    def visit_Call(self, node):
        # Only allow np.func_name(...) calls
        if not isinstance(node.func, ast.Attribute):
            raise ValueError("Only np.function() calls are allowed")
        return self._visit_np_call(node)

    def visit_Attribute(self, node):
        # Allow np.pi, np.e, np.inf (constants, not function calls)
        if isinstance(node.value, ast.Name) and node.value.id == "np":
            attr = node.attr
            if attr in _SAFE_NP_FUNCS:
                val = getattr(np, attr, None)
                if val is not None and not callable(val):
                    return val  # It's a constant like np.pi
                elif val is not None and callable(val):
                    # This path is hit when np.exp is used as a value (not called)
                    # which shouldn't happen in normal equations, but return it safely
                    return val
            raise ValueError(f"Unsupported numpy attribute: np.{attr}")
        raise ValueError("Only 'np' attribute access is allowed")

    def _visit_np_call(self, node):
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "np":
            raise ValueError("Only np.function() calls are allowed")
        
        func_name = node.func.attr
        if func_name not in _SAFE_NP_FUNCS:
            raise ValueError(f"Unsupported numpy function: np.{func_name}")
        
        func = getattr(np, func_name)
        if not callable(func):
            raise ValueError(f"np.{func_name} is not callable")

        args = [self.visit(arg) for arg in node.args]
        kwargs = {kw.arg: self.visit(kw.value) for kw in node.keywords}
        return func(*args, **kwargs)

    def visit_Compare(self, node):
        left = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            op_type = type(op)
            if op_type not in _SAFE_CMPOPS:
                raise ValueError(f"Unsupported comparison: {op_type.__name__}")
            right = self.visit(comparator)
            if not _SAFE_CMPOPS[op_type](left, right):
                return False
            left = right
        return True

    def visit_IfExp(self, node):
        # Allow ternary: a if cond else b
        test = self.visit(node.test)
        if test:
            return self.visit(node.body)
        return self.visit(node.orelse)

    def generic_visit(self, node):
        raise ValueError(f"Unsupported expression element: {type(node).__name__}")


def safe_eval(expression: str, variables: dict):
    """
    Safely evaluate a mathematical expression string.

    Args:
        expression: A math expression (e.g. "A1*np.exp(-b1*x) + c")
        variables: Dict mapping variable names to their values

    Returns:
        The result of evaluating the expression.

    Raises:
        ValueError: If the expression contains unsupported/unsafe elements.
    """
    try:
        tree = ast.parse(expression, mode='eval')
    except SyntaxError as e:
        raise ValueError(f"Invalid expression syntax: {e}") from e

    evaluator = _SafeEvaluator(variables)
    return evaluator.visit(tree)


def safe_make_function(equation_str: str, param_names: list):
    """
    Create a callable function from a math equation string — safe alternative to eval().

    Args:
        equation_str: Math expression using 'x' and param names (e.g. "A1*np.exp(-b1*x)")
        param_names: List of parameter names (e.g. ["A1", "b1"])

    Returns:
        A callable f(x, param1, param2, ...) suitable for scipy.optimize.curve_fit

    Raises:
        ValueError: If the equation contains unsafe elements.
    """
    # Validate the AST at creation time (fail fast)
    try:
        tree = ast.parse(equation_str, mode='eval')
    except SyntaxError as e:
        raise ValueError(f"Invalid equation syntax: {e}") from e

    # Walk the tree to check for unsafe nodes BEFORE any data is provided
    # (use dummy variables just for validation)
    dummy_vars = {"x": 1.0, "np": np}
    dummy_vars.update({name: 1.0 for name in param_names})
    try:
        _SafeEvaluator(dummy_vars).visit(tree)
    except Exception as e:
        raise ValueError(f"Equation validation failed: {e}") from e

    # Return a closure that evaluates safely each time
    def _safe_func(x, *params):
        if len(params) != len(param_names):
            raise ValueError(
                f"Expected {len(param_names)} parameters, got {len(params)}"
            )
        variables = {"x": x, "np": np}
        variables.update(dict(zip(param_names, params)))
        return _SafeEvaluator(variables).visit(tree)

    return _safe_func
