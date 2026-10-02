"""Cooperative Python AST runtime with hardware APIs, never host eval/exec.

Supports ordinary functions, loops, expressions and local helper modules.
Only explicitly simulated APIs are importable; no host files/network/processes.
"""
import ast
import math
import operator
import re
from pathlib import Path
from dataclasses import dataclass
from app.simulation.gpio_script import GpioScript,gpio_alias


@dataclass
class Function:
    node: object
    globals: dict


class Return(Exception):
    def __init__(self,value): self.value=value


class Break(Exception): pass
class Continue(Exception): pass


class PythonBoard(GpioScript):
    def __init__(self,source,definition,source_path=None):
        if len(source)>100000: raise ValueError("Python source is too large")
        self.tree=ast.parse(source)
        self.pins={a for p in definition.pins if (a:=gpio_alias(p.name))}
        self.physical={p.number:gpio_alias(p.name) for p in definition.pins}
        self.raspberry="Raspberry Pi" in definition.name and "Pico" not in definition.name
        self.env={}; self.locals=[]; self.global_names=[]
        self.states={}; self.inputs={}; self.time=0.; self.wake=0.; self.steps=0
        self.board_numbering=False; self.bus_write=None; self.serial=""
        self.root=Path(source_path).resolve().parent if source_path else None
        self.modules={}; self.lcds={}; self.depth=0
        for node in ast.walk(self.tree):
            if isinstance(node,(ast.ClassDef,ast.Lambda,ast.AsyncFunctionDef,ast.Await,ast.Yield,ast.YieldFrom)):
                raise ValueError("Unsupported Python syntax: "+type(node).__name__)
            if isinstance(node,ast.Attribute) and node.attr.startswith("_"):
                raise ValueError("Private Python attributes are not accessible")
            if isinstance(node,ast.FunctionDef) and (node.decorator_list or node.args.vararg or node.args.kwarg or node.args.kwonlyargs or node.args.posonlyargs):
                raise ValueError("Function decorators and expanded/keyword-only arguments are not supported")
        self.program=self.block(self.tree.body)

    def budget(self):
        self.steps+=1
        if self.steps>10000: raise ValueError("Python program must sleep/yield; instruction limit reached")

    def lookup(self,name):
        if self.locals and name in self.locals[-1]: return self.locals[-1][name]
        if name in self.env: return self.env[name]
        if name in {"range","len","str","int","float","bool","chr","ord","hex","bin","abs","min","max","round","list","tuple","bytes","enumerate","zip","print"}:
            return ("api",name)
        raise ValueError("Unknown Python variable: "+name)

    def assign(self,target,value):
        if isinstance(value,(str,list,tuple,dict,bytes)) and len(value)>100000: raise ValueError("Python value is too large")
        if isinstance(target,ast.Name):
            scope=self.locals[-1] if self.locals and target.id not in self.global_names[-1] else self.env
            scope[target.id]=value
        elif isinstance(target,(ast.Tuple,ast.List)):
            if len(value)!=len(target.elts): raise ValueError("Unpacking length mismatch")
            for item,part in zip(target.elts,value): self.assign(item,part)
        else: raise ValueError("Unsupported assignment target")

    def expr(self,node):
        # The runtime uses a generator for calls inside expressions, so sleep
        # in a helper function yields to the simulation rather than blocking Qt.
        raise ValueError("Use cooperative Python expressions")

    def evaluate(self,node):
        self.budget()
        if isinstance(node,ast.Constant): return node.value
        if isinstance(node,ast.Name): return self.lookup(node.id)
        if isinstance(node,(ast.List,ast.Tuple)):
            values=[]
            for item in node.elts: values.append((yield from self.evaluate(item)))
            return values if isinstance(node,ast.List) else tuple(values)
        if isinstance(node,ast.Dict):
            result={}
            for key,value in zip(node.keys,node.values): result[(yield from self.evaluate(key))]=yield from self.evaluate(value)
            return result
        if isinstance(node,ast.Attribute):
            base=yield from self.evaluate(node.value)
            if isinstance(base,dict) and node.attr in base: return base[node.attr]
            if isinstance(base,tuple) and base[0] in {"api","pin","lcd","bus"}:
                if node.attr in {"OUT","IN","BCM","BOARD","HIGH","LOW","PUD_UP","PUD_DOWN"}: return node.attr
                if base[0]=="lcd" and node.attr in {"cursor_pos","backlight_enabled"}: return self.lcds[base[1]][node.attr]
                return ("method",base,node.attr)
            if isinstance(base,str) and node.attr in {"format","upper","lower","strip","ljust","rjust","replace"}:
                return ("string",base,node.attr)
            raise ValueError("Unsupported Python attribute: "+node.attr)
        if isinstance(node,ast.Subscript):
            value=yield from self.evaluate(node.value)
            if isinstance(node.slice,ast.Slice):
                parts=[]
                for part in (node.slice.lower,node.slice.upper,node.slice.step): parts.append((yield from self.evaluate(part)) if part else None)
                return value[slice(*parts)]
            return value[(yield from self.evaluate(node.slice))]
        if isinstance(node,ast.UnaryOp):
            value=yield from self.evaluate(node.operand)
            ops={ast.Not:operator.not_,ast.USub:operator.neg,ast.UAdd:operator.pos,ast.Invert:operator.invert}
            return ops[type(node.op)](value)
        if isinstance(node,ast.BinOp):
            left=yield from self.evaluate(node.left); right=yield from self.evaluate(node.right)
            ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod,ast.BitOr:operator.or_,ast.BitAnd:operator.and_,ast.BitXor:operator.xor,ast.LShift:operator.lshift,ast.RShift:operator.rshift}
            if isinstance(node.op,(ast.LShift,ast.RShift)) and not 0<=right<=64: raise ValueError("Shift limit exceeded")
            if isinstance(node.op,ast.Mult) and isinstance(left,(str,list,tuple,bytes)) and len(left)*max(0,right)>100000: raise ValueError("Python value is too large")
            return ops[type(node.op)](left,right)
        if isinstance(node,ast.BoolOp):
            value=None
            for part in node.values:
                value=yield from self.evaluate(part)
                if isinstance(node.op,ast.And) and not value or isinstance(node.op,ast.Or) and value: break
            return value
        if isinstance(node,ast.Compare):
            left=yield from self.evaluate(node.left)
            ops={ast.Eq:operator.eq,ast.NotEq:operator.ne,ast.Lt:operator.lt,ast.LtE:operator.le,ast.Gt:operator.gt,ast.GtE:operator.ge,ast.In:lambda a,b:a in b,ast.NotIn:lambda a,b:a not in b}
            for op,part in zip(node.ops,node.comparators):
                right=yield from self.evaluate(part)
                if not ops[type(op)](left,right): return False
                left=right
            return True
        if isinstance(node,ast.IfExp): return (yield from self.evaluate(node.body if (yield from self.evaluate(node.test)) else node.orelse))
        if isinstance(node,ast.JoinedStr):
            parts=[]
            for part in node.values:
                if isinstance(part,ast.FormattedValue):
                    value=yield from self.evaluate(part.value)
                    spec=(yield from self.evaluate(part.format_spec)) if part.format_spec else ""
                    if len(spec)>30 or any(int(n)>100000 for n in re.findall(r"\d+",spec)): raise ValueError("Format limit exceeded")
                    parts.append(format(value,spec))
                else: parts.append(part.value)
            return "".join(parts)
        if isinstance(node,ast.Call):
            function=yield from self.evaluate(node.func); args=[]; kwargs={}
            for arg in node.args: args.append((yield from self.evaluate(arg)))
            for arg in node.keywords:
                if arg.arg is None: raise ValueError("Expanded keyword arguments are unsupported")
                kwargs[arg.arg]=yield from self.evaluate(arg.value)
            return (yield from self.call(function,args,kwargs))
        raise ValueError(f"Unsupported Python expression at line {getattr(node,'lineno',0)}")

    def call(self,function,args,kwargs):
        self.budget()
        if isinstance(function,Function):
            if self.depth>=32: raise ValueError("Python call depth limit exceeded")
            params=function.node.args.args
            if len(args)>len(params): raise ValueError("Too many function arguments")
            if any(key not in {param.arg for param in params} for key in kwargs): raise ValueError("Unknown function keyword argument")
            local={param.arg:value for param,value in zip(params,args)}; local.update(kwargs)
            defaults=function.node.args.defaults
            for param,default in zip(params[len(params)-len(defaults):],defaults):
                if param.arg not in local: local[param.arg]=yield from self.evaluate(default)
            if any(param.arg not in local for param in params): raise ValueError("Missing function argument")
            old_env=self.env; self.env=function.globals; self.locals.append(local); self.global_names.append(set()); self.depth+=1
            try:
                yield from self.block(function.node.body)
            except Return as result: return result.value
            finally:
                self.depth-=1; self.locals.pop(); self.global_names.pop(); self.env=old_env
            return None
        if not isinstance(function,tuple): raise ValueError("Object is not callable")
        if function[0]=="method":
            base,name=function[1:]
            if base[0]=="api": function=("api",base[1]+"."+name)
            elif base[0]=="pin":
                pin=base[1]
                if name in {"on","off","toggle"}: self.states[pin]=1 if name=="on" else 0 if name=="off" else 1-self.states.get(pin,0); return None
                if name=="value":
                    if args: self.states[pin]=int(bool(args[0])); return None
                    return int(self.inputs.get(pin,self.states.get(pin,0)==1))
            elif base[0]=="bus":
                if name in {"write_byte","write_byte_data","write_i2c_block_data"}:
                    values=[args[1]] if name=="write_byte" else [args[1],*args[2]] if name=="write_i2c_block_data" else [args[1],args[2]]
                    for value in values: self.write_bus(base[1],args[0],int(value)&255)
                    return None
                if name=="close": return None
            elif base[0]=="lcd": return self.lcd_call(base[1],name,args,kwargs)
            if base[0]!="api": raise ValueError("Unsupported simulated device call: "+name)
        if function[0]=="string":
            if function[2] in {"ljust","rjust"} and args and args[0]>100000: raise ValueError("String limit exceeded")
            if function[2]=="format" and ("__" in function[1] or any(int(n)>100000 for n in re.findall(r"\d+",function[1]))): raise ValueError("Format limit exceeded")
            return getattr(function[1],function[2])(*args,**kwargs)
        name=function[1]; short=name.rsplit(".",1)[-1]
        if short in {"sleep","sleep_ms"}:
            delay=float(args[0])/(1000 if short=="sleep_ms" else 1)
            if not math.isfinite(delay) or delay<=0: raise ValueError("sleep must be positive and finite")
            yield delay; return None
        if short in {"time","monotonic","ticks_ms"}: return self.time*(1000 if short=="ticks_ms" else 1)
        if short in {"Pin","LED","DigitalOutputDevice","DigitalInputDevice","Button"}:
            pin=self.pin(args[0] if args else kwargs["pin"])
            mode=args[1] if len(args)>1 else kwargs.get("mode","IN" if short in {"Button","DigitalInputDevice"} else "OUT")
            self.states[pin]=2 if mode=="IN" else int(bool(kwargs.get("initial_value",0)))
            return ("pin",pin)
        if short=="setmode": self.board_numbering=args[0]=="BOARD"; return None
        if short=="setup":
            for value in (args[0] if isinstance(args[0],(list,tuple)) else [args[0]]): self.states[self.pin(value)]=2 if args[1]=="IN" else int(kwargs.get("initial",0) not in {0,False,"LOW"})
            return None
        if short=="output":
            self.states[self.pin(args[0])]=int(args[1] not in {0,False,"LOW"}); return None
        if short=="input": return int(self.inputs.get(self.pin(args[0]),False))
        if short=="cleanup": self.states={pin:2 for pin in self.states}; return None
        if short=="setwarnings": return None
        if short in {"SMBus","I2C","SoftI2C"}: return ("bus",int(args[0] if args else kwargs.get("id",1)))
        if short=="CharLCD":
            if kwargs.get("i2c_expander",args[0] if args else "PCF8574")!="PCF8574": raise ValueError("Only PCF8574 LCD backpacks are supported")
            address=int(kwargs.get("address",args[1] if len(args)>1 else 0x27)); bus=int(kwargs.get("port",1))
            if kwargs.get("cols",16)!=16 or kwargs.get("rows",2)!=2: raise ValueError("LCD model supports 16x2 only")
            self.lcds[address]={"bus":bus,"cursor_pos":(0,0),"backlight_enabled":bool(kwargs.get("backlight_enabled",True))}
            self.write_nibble(address,3); self.write_nibble(address,3); self.write_nibble(address,2)
            for value in (0x28,0x0c,1,6): self.write_lcd(address,value)
            return ("lcd",address)
        if name=="print": self.serial+=(" ".join(map(str,args))+"\n")[:4096-len(self.serial)]; return None
        builtins={"range":range,"len":len,"str":str,"int":int,"float":float,"bool":bool,"chr":chr,"ord":ord,"hex":hex,"bin":bin,"abs":abs,"min":min,"max":max,"round":round,"list":list,"tuple":tuple,"bytes":bytes,"enumerate":lambda x:list(enumerate(x)),"zip":lambda *x:list(zip(*x))}
        if name in builtins:
            if name=="bytes" and args and isinstance(args[0],int) and args[0]>100000: raise ValueError("Bytes limit exceeded")
            value=builtins[name](*args,**kwargs)
            if hasattr(value,"__len__") and len(value)>100000: raise ValueError("Python collection limit exceeded")
            return value
        raise ValueError("Unsupported simulated Python API: "+name)

    def write_bus(self,bus,address,value):
        if self.bus_write is None: raise ValueError("No circuit is connected to the I2C API")
        self.bus_write(bus,address,value)

    def write_nibble(self,address,nibble,rs=0):
        info=self.lcds[address]; value=(nibble<<4)|rs|(8 if info["backlight_enabled"] else 0)
        self.write_bus(info["bus"],address,value|4); self.write_bus(info["bus"],address,value)

    def write_lcd(self,address,value,rs=0):
        self.write_nibble(address,value>>4,rs); self.write_nibble(address,value&15,rs)

    def lcd_call(self,address,name,args,kwargs):
        info=self.lcds[address]
        if name in {"clear","home"}: self.write_lcd(address,1 if name=="clear" else 2); info["cursor_pos"]=(0,0)
        elif name=="write_string":
            from unicodedata import normalize
            row,col=info["cursor_pos"]
            for character in normalize("NFC",str(args[0])):
                if character=="\n": row=(row+1)%2; continue
                if character=="\r": col=0; continue
                self.write_lcd(address,0x80|(row*0x40+col))
                for byte in character.encode("utf-8"): self.write_lcd(address,byte,1)
                col+=1
                if col==16: col=0; row=(row+1)%2
            info["cursor_pos"]=(row,col)
        elif name=="close":
            if kwargs.get("clear",False): self.write_lcd(address,1)
        else: raise ValueError("Unsupported LCD method: "+name)

    def import_module(self,name):
        known={"time","machine","gpiozero","RPi.GPIO","electroschem","smbus","smbus2","RPLCD.i2c"}
        if name in known: return ("api",name)
        if name in self.modules: return self.modules[name]
        if self.root is None or not name.isidentifier() or name.startswith("_") or len(self.modules)>=16:
            raise ValueError("Unsupported Python import: "+name)
        path=(self.root/(name+".py")).resolve()
        if path.parent!=self.root or not path.is_file() or path.stat().st_size>100000:
            raise ValueError("Only local Python helper modules and simulated hardware APIs can be imported: "+name)
        namespace={}; self.modules[name]=namespace; old=self.env; old_locals=self.locals; old_globals=self.global_names
        self.env=namespace; self.locals=[]; self.global_names=[]
        try: yield from self.block(ast.parse(path.read_text(encoding="utf-8-sig")).body)
        finally: self.env=old; self.locals=old_locals; self.global_names=old_globals
        return namespace

    def block(self,statements):
        for node in statements:
            self.budget()
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                for alias in node.names:
                    module=yield from self.import_module(alias.name if isinstance(node,ast.Import) else node.module)
                    value=module if isinstance(node,ast.Import) else module[alias.name] if isinstance(module,dict) else ("api",module[1]+"."+alias.name)
                    self.assign(ast.Name(id=alias.asname or alias.name,ctx=ast.Store()),value)
            elif isinstance(node,ast.FunctionDef):
                if node.decorator_list or node.args.vararg or node.args.kwarg or node.args.kwonlyargs or node.args.posonlyargs:
                    raise ValueError("Function decorators and expanded/keyword-only arguments are not supported")
                self.assign(ast.Name(id=node.name,ctx=ast.Store()),Function(node,self.env))
            elif isinstance(node,ast.Assign):
                value=yield from self.evaluate(node.value)
                for target in node.targets:
                    if isinstance(target,ast.Attribute):
                        obj=yield from self.evaluate(target.value)
                        if not isinstance(obj,tuple) or obj[0]!="lcd" or target.attr not in {"cursor_pos","backlight_enabled"}: raise ValueError("Unsupported device property assignment")
                        self.lcds[obj[1]][target.attr]=value
                        if target.attr=="cursor_pos": self.write_lcd(obj[1],0x80|(int(value[0])*0x40+int(value[1])))
                        else: self.write_bus(self.lcds[obj[1]]["bus"],obj[1],8 if value else 0)
                    else: self.assign(target,value)
            elif isinstance(node,ast.AugAssign):
                value=yield from self.evaluate(ast.BinOp(left=node.target,op=node.op,right=node.value)); self.assign(node.target,value)
            elif isinstance(node,ast.Expr): yield from self.evaluate(node.value)
            elif isinstance(node,ast.If): yield from self.block(node.body if (yield from self.evaluate(node.test)) else node.orelse)
            elif isinstance(node,ast.While):
                while (yield from self.evaluate(node.test)):
                    self.budget()
                    try: yield from self.block(node.body)
                    except Continue: continue
                    except Break: break
                else: yield from self.block(node.orelse)
            elif isinstance(node,ast.For):
                values=yield from self.evaluate(node.iter)
                for value in values:
                    self.budget(); self.assign(node.target,value)
                    try: yield from self.block(node.body)
                    except Continue: continue
                    except Break: break
                else: yield from self.block(node.orelse)
            elif isinstance(node,ast.Return): raise Return((yield from self.evaluate(node.value)) if node.value else None)
            elif isinstance(node,ast.Break): raise Break()
            elif isinstance(node,ast.Continue): raise Continue()
            elif isinstance(node,ast.Global):
                if self.global_names: self.global_names[-1].update(node.names)
            elif isinstance(node,ast.Pass): pass
            else: raise ValueError("Unsupported Python statement: "+type(node).__name__)

    def advance(self,dt,inputs=None):
        target=self.time+dt; self.inputs=inputs or {}; self.steps=0
        while self.wake<=target:
            self.time=self.wake
            try: self.wake+=next(self.program)
            except StopIteration: self.wake=math.inf; break
        self.time=target
        return dict(self.states)
