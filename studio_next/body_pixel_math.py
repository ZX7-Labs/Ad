"""Bounded numerical image expressions. No eval, Python code, I/O or imports.

Expressions describe pixel mathematics, like a compositor's math nodes. They
cannot add BODY capabilities, launch software or modify implementation code.
"""
from __future__ import annotations
import ast
import operator
from .body_animation import finite_number

_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod}
_COMPARE = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt,
            ast.GtE: operator.ge, ast.Eq: operator.eq, ast.NotEq: operator.ne}
FUNCTION_ARITY = {"sin":1,"cos":1,"tan":1,"sqrt":1,"abs":1,"exp":1,"log":1,
    "floor":1,"ceil":1,"min":2,"max":2,"atan2":2,"pow":2,"clamp":3,"mix":3,"where":3,"smoothstep":3}
BASE_VARIABLES = frozenset({"x","y","u","v","width","height","frame","time","pi"})


class PixelExpression:
    def __init__(self, text, variables, *, max_nodes=512, max_depth=32):
        if not isinstance(text, str) or not text or len(text) > 4096:
            raise ValueError("Pixel expression is empty or exceeds host length budget")
        try:
            self.tree = ast.parse(text, mode="eval").body
        except (SyntaxError, RecursionError) as exc:
            raise ValueError("Invalid pixel mathematics") from exc
        self.names, self.node_count = set(), 0
        def check(node, depth):
            self.node_count += 1
            if self.node_count > max_nodes or depth > max_depth:
                raise ValueError("Pixel expression exceeds host complexity budget")
            if isinstance(node, ast.Constant):
                finite_number(node.value, "Pixel constant")
                if abs(node.value) > 1e12:
                    raise ValueError("Pixel constant exceeds numerical range")
            elif isinstance(node, ast.Name):
                if node.id not in variables:
                    raise ValueError("Unknown pixel variable: " + node.id)
                self.names.add(node.id)
            elif isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
                check(node.left, depth+1); check(node.right, depth+1)
            elif isinstance(node, ast.UnaryOp) and type(node.op) in (ast.UAdd, ast.USub):
                check(node.operand, depth+1)
            elif isinstance(node, ast.Compare) and len(node.ops)==1 and type(node.ops[0]) in _COMPARE:
                check(node.left, depth+1); check(node.comparators[0], depth+1)
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                  and node.func.id in FUNCTION_ARITY and not node.keywords
                  and len(node.args)==FUNCTION_ARITY[node.func.id]):
                for child in node.args: check(child, depth+1)
            else:
                raise ValueError("Only declared scalar/pixel mathematics is executable")
        check(self.tree, 0)

    def evaluate(self, variables):
        import numpy as np
        def smoothstep(a,b,x):
            t=np.clip((x-a)/(b-a),0,1)
            return t*t*(3-2*t)
        functions={"sin":np.sin,"cos":np.cos,"tan":np.tan,"sqrt":np.sqrt,"abs":np.abs,
            "exp":np.exp,"log":np.log,"floor":np.floor,"ceil":np.ceil,"min":np.minimum,
            "max":np.maximum,"atan2":np.arctan2,"pow":np.power,"clamp":np.clip,"where":np.where,
            "mix":lambda a,b,t:a*(1-t)+b*t,"smoothstep":smoothstep}
        def run(node):
            if isinstance(node,ast.Constant): return np.float32(node.value)
            if isinstance(node,ast.Name): return variables[node.id]
            if isinstance(node,ast.BinOp): return _BINARY[type(node.op)](run(node.left),run(node.right))
            if isinstance(node,ast.UnaryOp):
                value=run(node.operand)
                return -value if isinstance(node.op,ast.USub) else value
            if isinstance(node,ast.Compare): return _COMPARE[type(node.ops[0])](run(node.left),run(node.comparators[0]))
            return functions[node.func.id](*(run(child) for child in node.args))
        with np.errstate(over="ignore",invalid="ignore",divide="ignore"):
            result=np.asarray(run(self.tree),dtype=np.float32)
        if not np.all(np.isfinite(result)):
            raise ValueError("Pixel expression produced non-finite values")
        return result
