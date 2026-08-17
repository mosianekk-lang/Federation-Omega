from __future__ import annotations

import ast
import math
import operator
from dataclasses import dataclass
from typing import Callable


class MathExpressionError(ValueError):
    pass


@dataclass(frozen=True)
class MathResult:
    expression: str
    value: float
    engine: str = "deterministic-safe-ast-v1"


_BINARY: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY: dict[type[ast.unaryop], Callable[[float], float]] = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCTIONS: dict[str, Callable[..., float]] = {
    "abs": abs,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
}
_CONSTANTS = {"pi": math.pi, "e": math.e}


def calculate(expression: str) -> MathResult:
    source = expression.strip()
    if not source or len(source) > 512:
        raise MathExpressionError("EXPRESSION_SIZE_INVALID")
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as exc:
        raise MathExpressionError("EXPRESSION_SYNTAX_INVALID") from exc
    if sum(1 for _ in ast.walk(tree)) > 64:
        raise MathExpressionError("EXPRESSION_COMPLEXITY_EXCEEDED")

    def evaluate(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            return _UNARY[type(node.op)](evaluate(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise MathExpressionError("EXPONENT_OUT_OF_BOUNDS")
            try:
                value = _BINARY[type(node.op)](left, right)
            except (ArithmeticError, ValueError, OverflowError) as exc:
                raise MathExpressionError("ARITHMETIC_DOMAIN_ERROR") from exc
            if isinstance(value, complex) or not math.isfinite(float(value)):
                raise MathExpressionError("NONFINITE_RESULT")
            return float(value)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS:
            if node.keywords or len(node.args) not in {1, 2}:
                raise MathExpressionError("FUNCTION_ARGUMENTS_INVALID")
            try:
                value = _FUNCTIONS[node.func.id](*(evaluate(argument) for argument in node.args))
            except (ArithmeticError, ValueError, OverflowError) as exc:
                raise MathExpressionError("ARITHMETIC_DOMAIN_ERROR") from exc
            if not math.isfinite(float(value)):
                raise MathExpressionError("NONFINITE_RESULT")
            return float(value)
        raise MathExpressionError("EXPRESSION_NODE_FORBIDDEN")

    return MathResult(expression=source, value=evaluate(tree))
