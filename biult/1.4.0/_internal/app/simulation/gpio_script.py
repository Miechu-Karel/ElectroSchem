"""Small, bounded GPIO Python interpreter; never executes host Python code.

Supports sequential GPIO writes, reads, sleep, if and while, gpiozero LED,
machine.Pin and RPi.GPIO syntax. It is a behavioural model, not a CPU/OS
emulator. Unknown syntax raises an error rather than silently doing nothing.
"""
import ast
import math


def gpio_alias(name):
    import re
    # Prefer the silicon GPIO label when a board exposes an Arduino alias too.
    names = name.split("/")
    for part in names:
        if re.fullmatch(r"GPIO\d+", part): return part
    for part in names:
        if re.fullmatch(r"(?:GP|D|A|P)\d+|P[A-Z]\d+|GPIO[A-Z_0-9]+", part): return part
    return None


class GpioScript:
    def __init__(self, source, definition):
        if len(source) > 100000: raise ValueError("GPIO source is too large")
        self.tree = ast.parse(source)
        self.pins = {a for p in definition.pins if (a := gpio_alias(p.name))}
        self.physical = {p.number: gpio_alias(p.name) for p in definition.pins}
        self.raspberry = "Raspberry Pi" in definition.name and "Pico" not in definition.name
        self.env = {}; self.states = {}; self.inputs = {}; self.time = 0.; self.wake = 0.
        self.board_numbering = False
        self.steps = 0
        # Reject imports/constructs that are not part of the simulated API.
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and node.keywords:
                raise ValueError("GPIO subset currently supports positional arguments only")
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module]
                if any(n not in {"time", "machine", "gpiozero", "RPi.GPIO", "electroschem"} for n in names):
                    raise ValueError("Only simulated GPIO/time imports are supported")
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.With, ast.Try, ast.For, ast.Lambda, ast.Subscript)):
                raise ValueError(f"Unsupported GPIO syntax: {type(node).__name__}")
        self.program = self.block(self.tree.body)

    def pin(self, value):
        if isinstance(value, tuple): return value[1]
        text = str(value)
        if self.board_numbering and text.isdigit(): text = self.physical.get(text)
        elif text.isdigit():
            text = ("GPIO" if any(p=="GPIO"+text for p in self.pins) else "GP" if "GP"+text in self.pins else "D")+text
        if text not in self.pins: raise ValueError(f"Unknown GPIO pin: {value}")
        return text

    def expr(self, node):
        if isinstance(node, ast.Constant): return node.value
        if isinstance(node, ast.Name):
            if node.id in self.env: return self.env[node.id]
            if node.id in {"True", "False"}: return node.id == "True"
            raise ValueError(f"Unknown GPIO variable: {node.id}")
        if isinstance(node, ast.Attribute):
            base = self.expr(node.value)
            if node.attr in {"OUT", "IN", "BCM", "BOARD", "HIGH", "LOW", "PUD_UP", "PUD_DOWN"}: return node.attr
            return (base, node.attr)
        if isinstance(node, ast.UnaryOp):
            value = self.expr(node.operand)
            if isinstance(node.op, ast.Not): return not value
            if isinstance(node.op, ast.USub): return -value
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            a,b=self.expr(node.left),self.expr(node.comparators[0])
            if isinstance(node.ops[0], ast.Eq): return a==b
            if isinstance(node.ops[0], ast.NotEq): return a!=b
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
            args = [self.expr(n) for n in node.args]
            if name in {"LED", "Pin"}:
                p = self.pin(args[0]); self.states[p] = 2 if len(args)>1 and args[1]=="IN" else 0
                return ("pin", p)
            if name in {"input", "value"}:
                p=self.pin(args[0]) if name=="input" else self.pin(self.expr(node.func.value))
                if name=="value" and args:
                    self.states[p]=int(bool(args[0])); return None
                return self.inputs.get(p, self.states.get(p,0)==1)
        raise ValueError(f"Unsupported GPIO expression at line {getattr(node,'lineno',0)}")

    def block(self, statements):
        for node in statements:
            self.steps += 1
            if self.steps > 10000: raise ValueError("GPIO program must sleep/yield; instruction limit reached")
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # Record aliases without importing a module in this process.
                for a in node.names: self.env[a.asname or a.name]=a.name
            elif isinstance(node, ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
                self.env[node.targets[0].id] = self.expr(node.value)
            elif isinstance(node, ast.While):
                while self.expr(node.test):
                    self.steps += 1
                    if self.steps > 10000: raise ValueError("GPIO loop must sleep/yield")
                    yield from self.block(node.body)
            elif isinstance(node, ast.If):
                yield from self.block(node.body if self.expr(node.test) else node.orelse)
            elif isinstance(node, ast.Pass): pass
            elif isinstance(node, ast.Expr) and isinstance(node.value,ast.Constant): pass
            elif isinstance(node, ast.Expr) and isinstance(node.value,ast.Call):
                call=node.value
                name=call.func.id if isinstance(call.func,ast.Name) else call.func.attr
                args=[self.expr(n) for n in call.args]
                if name in {"sleep", "sleep_ms"}:
                    delay=float(args[0])/(1000 if name=="sleep_ms" else 1)
                    if not math.isfinite(delay) or delay<=0: raise ValueError("sleep must be positive and finite")
                    yield delay
                elif name=="setmode": self.board_numbering=args[0]=="BOARD"
                elif name=="setup":
                    p=self.pin(args[0]); self.states[p]=0 if args[1]=="OUT" else 2
                elif name=="output":
                    self.states[self.pin(args[0])]=int(args[1] not in {0,False,"LOW"})
                elif name in {"on","off","toggle"}:
                    p=self.pin(self.expr(call.func.value))
                    self.states[p]=1 if name=="on" else 0 if name=="off" else 1-self.states.get(p,0)
                elif name=="value": self.expr(call)
                elif name=="cleanup": self.states={p:2 for p in self.states}
                elif name=="setwarnings": pass
                else: raise ValueError(f"Unsupported GPIO call: {name} (line {node.lineno})")
            else: raise ValueError(f"Unsupported GPIO statement: {type(node).__name__}")

    def advance(self, dt, inputs=None):
        target=self.time+dt; self.inputs=inputs or {}; self.steps=0
        while self.wake <= target:
            try: self.wake += next(self.program)
            except StopIteration: self.wake=math.inf; break
        self.time=target
        return dict(self.states)
